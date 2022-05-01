# Copyright (c) 2013 Calin Crisan
# This file is part of motionEye.
#
# motionEye is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import ftplib
import io
import json
import logging
import mimetypes
import os
import os.path
import time
from base64 import b64encode
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request

import boto3
import pycurl

from motioneye import settings, utils

_STATE_FILE_NAME = 'uploadservices.json'
_services = None


class UploadService:
    MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1GB

    NAME = 'base'

    def __init__(self, camera_id, **kwargs):
        self.camera_id = camera_id

    def __str__(self):
        return self.NAME

    @classmethod
    def get_authorize_url(cls):
        return '/'

    def test_access(self):
        return True

    def upload_file(self, target_dir, filename, camera_name):
        ctime = os.path.getctime(filename)

        if target_dir:
            target_dir = os.path.realpath(target_dir)
            rel_filename = os.path.realpath(filename)
            rel_filename = rel_filename[len(target_dir) :]

            while rel_filename.startswith('/'):
                rel_filename = rel_filename[1:]

            self.debug(f'uploading file "{target_dir}/{rel_filename}" to {self}')

        else:
            rel_filename = os.path.basename(filename)

            self.debug(f'uploading file "{filename}" to {self}')

        try:
            st = os.stat(filename)

        except Exception as e:
            msg = f'failed to open file "{filename}": {e}'
            self.error(msg)
            raise Exception(msg)

        if st.st_size > self.MAX_FILE_SIZE:
            msg = 'file "{}" is too large ({}MB/{}MB)'.format(
                filename,
                st.st_size / 1024 / 1024,
                self.MAX_FILE_SIZE / 1024 / 1024,
            )

            self.error(msg)
            raise Exception(msg)

        try:
            f = open(filename, 'rb')

        except Exception as e:
            msg = f'failed to open file "{filename}": {e}'
            self.error(msg)
            raise Exception(msg)

        data = f.read()
        self.debug(f'size of "{filename}" is {len(data) / 1024.0 / 1024:.3f}MB')

        mime_type = mimetypes.guess_type(filename)[0] or 'image/jpeg'
        self.debug(f'mime type of "{filename}" is "{mime_type}"')

        self.upload_data(rel_filename, mime_type, data, ctime, camera_name)

        self.debug(f'file "{filename}" successfully uploaded')

    def upload_data(self, filename, mime_type, data, ctime, camera_name):
        pass

    def dump(self):
        return {}

    def load(self, data):
        pass

    def save(self):
        services = _load()
        camera_services = services.setdefault(self.camera_id, {})
        camera_services[self.NAME] = self

        _save(services)

    def log(self, level, message, **kwargs):
        message = self.NAME + ': ' + message

        logging.log(level, message, **kwargs)

    def debug(self, message, **kwargs):
        self.log(logging.DEBUG, message, **kwargs)

    def info(self, message, **kwargs):
        self.log(logging.INFO, message, **kwargs)

    def error(self, message, **kwargs):
        self.log(logging.ERROR, message, **kwargs)

    def clean_cloud(self, cloud_dir, local_folders):
        pass

    @staticmethod
    def get_service_classes():
        return {c.NAME: c for c in UploadService.__subclasses__()}


class GoogleBase:

    AUTH_URL = 'https://accounts.google.com/o/oauth2/auth'
    TOKEN_URL = 'https://accounts.google.com/o/oauth2/token'

    CLIENT_ID = (
        '349038943026-m16svdadjrqc0c449u4qv71v1m1niu5o.apps.googleusercontent.com'
    )
    CLIENT_NOT_SO_SECRET = 'jjqbWmICpA0GvbhsJB3okX7s'

    def _init(self):
        self._location = None
        self._authorization_key = None
        self._credentials = None
        self._folder_ids = {}
        self._folder_id_times = {}

    @classmethod
    def _get_authorize_url(cls):
        query = {
            'scope': cls.SCOPE,
            'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
            'response_type': 'code',
            'client_id': cls.CLIENT_ID,
            'access_type': 'offline',
        }

        return cls.AUTH_URL + '?' + urlencode(query)

    def _test_access(self):
        try:
            self._folder_ids = {}
            self._get_folder_id()
            return True

        except Exception as e:
            return str(e)

    def _dump(self):
        return {
            'location': self._location,
            'credentials': self._credentials,
            'authorization_key': self._authorization_key,
        }

    def _load(self, data):
        if data.get('location'):
            self._location = data['location']
            self._folder_ids = {}
        if data.get('authorization_key'):
            self._authorization_key = data['authorization_key']
            self._credentials = None
        if data.get('credentials'):
            self._credentials = data['credentials']

    def _request(self, url, body=None, headers=None, retry_auth=True, method=None):
        if not self._credentials:
            if not self._authorization_key:
                msg = 'missing authorization key'
                self.error(msg)
                raise Exception(msg)

            self.debug('requesting credentials')
            try:
                self._credentials = self._request_credentials(self._authorization_key)
                self.save()

            except Exception as e:
                self.error(f'failed to obtain credentials: {e}')
                raise

        headers = headers or {}
        headers['Authorization'] = f'Bearer {self._credentials["access_token"]}'

        self.debug(f'requesting {url}')
        request = Request(url, data=body, headers=headers)
        if method:
            request.get_method = lambda: method
        try:
            response = utils.urlopen(request)

        except HTTPError as e:
            if (
                e.code == 401 and retry_auth
            ):  # unauthorized, access token may have expired
                try:
                    self.debug('credentials have probably expired, refreshing them')
                    self._credentials = self._refresh_credentials(
                        self._credentials['refresh_token']
                    )
                    self.save()

                    # retry the request with refreshed credentials
                    return self._request(url, body, headers, retry_auth=False)

                except Exception:
                    self.error('refreshing credentials failed')
                    raise

            else:
                try:
                    e = json.load(e)
                    msg = e['error']['message']

                except Exception:
                    msg = str(e)

                self.error(f'request failed: {msg}')
                raise Exception(msg)

        except Exception as e:
            self.error(f'request failed: {e}')
            raise

        return response.read()

    def _request_json(self, url, body=None, headers=None, retry_auth=True, method=None):
        response = self._request(url, body, headers, retry_auth, method)
        try:
            response = json.loads(response)
        except Exception:
            self.error("response doesn't seem to be a valid json")
            raise

        return response

    def _request_credentials(self, authorization_key):
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        body = {
            'code': authorization_key,
            'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
            'client_id': self.CLIENT_ID,
            'client_secret': self.CLIENT_NOT_SO_SECRET,
            'scope': self.SCOPE,
            'grant_type': 'authorization_code',
        }
        body = urlencode(body).encode()

        request = Request(self.TOKEN_URL, data=body, headers=headers)

        try:
            response = utils.urlopen(request)

        except HTTPError as e:
            error = json.load(e)
            raise Exception(
                error.get('error_description') or error.get('error') or str(e)
            )

        data = json.load(response)

        return {
            'access_token': data['access_token'],
            'refresh_token': data['refresh_token'],
        }

    def _refresh_credentials(self, refresh_token):
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        body = {
            'refresh_token': refresh_token,
            'client_id': self.CLIENT_ID,
            'client_secret': self.CLIENT_NOT_SO_SECRET,
            'grant_type': 'refresh_token',
        }
        body = urlencode(body).encode()

        request = Request(self.TOKEN_URL, data=body, headers=headers)

        try:
            response = utils.urlopen(request)

        except HTTPError as e:
            error = json.load(e)
            raise Exception(
                error.get('error_description') or error.get('error') or str(e)
            )

        data = json.load(response)

        return {
            'access_token': data['access_token'],
            'refresh_token': data.get('refresh_token', refresh_token),
        }


class GoogleDrive(UploadService, GoogleBase):
    NAME = 'gdrive'

    SCOPE = 'https://www.googleapis.com/auth/drive.file'
    CHILDREN_URL = (
        'https://www.googleapis.com/drive/v2/files/%(parent_id)s/children?q=%(query)s'
    )
    CHILDREN_QUERY = (
        "'%(parent_id)s' in parents and title = '%(child_name)s' and trashed = false"
    )
    UPLOAD_URL = 'https://www.googleapis.com/upload/drive/v2/files?uploadType=multipart'
    CREATE_FOLDER_URL = 'https://www.googleapis.com/drive/v2/files'

    BOUNDARY = 'motioneye_multipart_boundary'

    FOLDER_ID_LIFE_TIME = 300  # 5 minutes

    def __init__(self, camera_id):
        self._init()

        UploadService.__init__(self, camera_id)

    @classmethod
    def get_authorize_url(cls):
        return cls._get_authorize_url()

    def test_access(self):
        return self._test_access()

    def upload_data(self, filename, mime_type, data, ctime, camera_name):
        path = os.path.dirname(filename)
        filename = os.path.basename(filename)

        metadata = {'title': filename, 'parents': [{'id': self._get_folder_id(path)}]}

        body = [
            '--' + self.BOUNDARY,
            'Content-Type: application/json; charset=UTF-8',
            '',
            json.dumps(metadata),
            '',
            '--' + self.BOUNDARY,
            f'Content-Type: {mime_type}',
            '',
            '',
        ]

        body = '\r\n'.join(body)
        body += data
        body += f'\r\n--{self.BOUNDARY}--'

        headers = {
            'Content-Type': f'multipart/related; boundary="{self.BOUNDARY}"',
            'Content-Length': len(body),
        }

        self._request(self.UPLOAD_URL, body, headers)

    def dump(self):
        return self._dump()

    def load(self, data):
        self._load(data)

    def _get_folder_id(self, path=''):
        now = time.time()

        folder_id = self._folder_ids.get(path)
        folder_id_time = self._folder_id_times.get(path, 0)

        location = self._location
        if not location.endswith('/'):
            location += '/'

        location += path

        if not folder_id or (now - folder_id_time > self.FOLDER_ID_LIFE_TIME):
            self.debug(f'finding folder id for location "{location}"')
            folder_id = self._get_folder_id_by_path(location)

            self._folder_ids[path] = folder_id
            self._folder_id_times[path] = now

        return folder_id

    def _get_folder_id_by_path(self, path):
        if path and path != '/':
            path = [p.strip() for p in path.split('/') if p.strip()]
            parent_id = 'root'
            for name in path:
                parent_id = self._get_folder_id_by_name(parent_id, name)

            return parent_id

        else:  # root folder
            return self._get_folder_id_by_name(None, 'root')

    def _get_folder_id_by_name(self, parent_id, child_name, create=True):
        if parent_id:
            query = self.CHILDREN_QUERY % {
                'parent_id': parent_id,
                'child_name': child_name,
            }
            query = quote(query)

        else:
            query = ''

        parent_id = parent_id or 'root'
        # when requesting the id of the root folder, we perform a dummy request,
        # event though we already know the id (which is "root"), to test the request

        url = self.CHILDREN_URL % {'parent_id': parent_id, 'query': query}
        response = self._request(url)
        try:
            response = json.loads(response)

        except Exception:
            self.error("response doesn't seem to be a valid json")
            raise

        if parent_id == 'root' and child_name == 'root':
            return 'root'

        items = response.get('items')
        if not items:
            if create:
                self.debug(
                    f'folder with name "{child_name}" does not exist, creating it'
                )
                self._create_folder(parent_id, child_name)
                return self._get_folder_id_by_name(parent_id, child_name, create=False)

            else:
                msg = f'folder with name "{child_name}" does not exist'
                self.error(msg)
                raise Exception(msg)

        return items[0]['id']

    def _create_folder(self, parent_id, child_name):
        metadata = {
            'title': child_name,
            'parents': [{'id': parent_id}],
            'mimeType': 'application/vnd.google-apps.folder',
        }

        body = json.dumps(metadata)

        headers = {'Content-Type': 'application/json; charset=UTF-8'}

        self._request(self.CREATE_FOLDER_URL, body, headers)

    def clean_cloud(self, cloud_dir, local_folders):
        # remove old cloud folder that does not exist in local.
        # assumes 'cloud_dir' is a direct child of the 'root'.

        removed_count = 0
        folder_id = self._get_folder_id_by_name('root', cloud_dir, False)
        children = self._get_children(folder_id)
        self.info(
            f'found {len(local_folders)}/{len(children)} folder(s) in local/cloud'
        )
        self.debug(f'local {local_folders}')
        for child in children:
            id = child['id']
            name = self._get_file_title(id)
            self.debug(f"cloud '{name}'")
            to_delete = not exist_in_local(name, local_folders)
            if to_delete and self._delete_file(id):
                removed_count += 1
                self.info(f"deleted a cloud folder '{name}'")

        self.info(f'deleted {removed_count} cloud folder(s)')
        return removed_count

    def _get_children(self, file_id):
        url = f'{self.CREATE_FOLDER_URL}/{file_id}/children'
        response = self._request(url)

        try:
            response = json.loads(response)

        except Exception:
            self.error("response doesn't seem to be a valid json")
            raise

        return response['items']

    def _delete_file(self, file_id):
        url = f'{self.CREATE_FOLDER_URL}/{file_id}'
        response = self._request(url, None, None, True, 'DELETE')
        succeeded = response == ""
        return succeeded

    def _get_file_metadata(self, file_id):
        url = f'{self.CREATE_FOLDER_URL}/{file_id}'
        response = self._request(url)

        try:
            response = json.loads(response)

        except Exception:
            self.error("response doesn't seem to be a valid json")
            raise

        return response

    def _get_file_title(self, file_id):
        return self._get_file_metadata(file_id)['title']


class GooglePhoto(UploadService, GoogleBase):
    NAME = 'gphoto'

    SCOPE = 'https://www.googleapis.com/auth/photoslibrary'
    GOOGLE_PHOTO_API = 'https://photoslibrary.googleapis.com/v1/'

    def __init__(self, camera_id):
        self._init()

        UploadService.__init__(self, camera_id)

    @classmethod
    def get_authorize_url(cls):
        return cls._get_authorize_url()

    def test_access(self):
        return self._test_access()

    def upload_data(self, filename, mime_type, data, ctime, camera_name):
        path = os.path.dirname(filename)
        filename = os.path.basename(filename)
        dayinfo = datetime.datetime.fromtimestamp(ctime).strftime('%Y-%m-%d')
        uploadname = dayinfo + '-' + filename

        body = data

        headers = {
            'Content-Type': 'application/octet-stream',
            'X-Goog-Upload-File-Name': uploadname,
            'X-Goog-Upload-Protocol': 'raw',
        }

        uploadToken = self._request(self.GOOGLE_PHOTO_API + 'uploads', body, headers)
        response = self._create_media(uploadToken, camera_name)
        self.debug(f'response {response["mediaItem"]}')

    def dump(self):
        return self._dump()

    def load(self, data):
        self._load(data)

    def _get_folder_id(self, path=''):
        location = self._location

        folder_id = self._folder_ids.get(location)

        self.debug(f'_get_folder_id({path}, {location}, {folder_id})')

        if not folder_id:
            self.debug(f'finding album with title "{location}"')
            folder_id = self._get_folder_id_by_name(location)

            self._folder_ids[location] = folder_id

        return folder_id

    def _get_folder_id_by_name(self, name, create=True):
        try:
            albums = self._get_albums()
            albumsWithName = self._filter_albums(albums, name)

            if albumsWithName:
                count = len(albumsWithName)
                if count > 0:
                    albumId = albumsWithName[0].get('id')
                    self.debug(
                        f'found {count} existing album(s) "{name}" taking first id "{albumId}"'
                    )
                    return albumId

            # create album
            response = self._create_folder(None, name)
            albumId = response.get('id')
            self.info(f'Album "{name}" was created successfully with id "{albumId}"')
            return albumId

        except Exception as e:
            self.error(f"_get_folder_id_by_name() failed: {e}")
            raise

    def _create_folder(self, parent_id, child_name):
        metadata = {'album': {'title': child_name}}

        body = json.dumps(metadata)

        headers = {'Content-Type': 'application/json'}

        response = self._request_json(self.GOOGLE_PHOTO_API + 'albums', body, headers)
        return response

    def _create_media(self, uploadToken, camera_name):
        description = 'captured by motionEye camera' + (
            f' "{camera_name}"' if camera_name else ''
        )

        metadata = {
            'albumId': self._get_folder_id(),
            'newMediaItems': [
                {
                    'description': description,
                    'simpleMediaItem': {'uploadToken': uploadToken},
                }
            ],
        }

        body = json.dumps(metadata)

        headers = {'Content-Type': 'application/json'}

        response = self._request_json(
            self.GOOGLE_PHOTO_API + 'mediaItems:batchCreate', body, headers
        )
        return response.get('newMediaItemResults')[0]

    def _get_albums(self):
        response = self._request_json(self.GOOGLE_PHOTO_API + 'albums')

        albums = response.get('albums')
        self.debug(f'got {len(albums)} album(s)')
        return albums

    def _filter_albums(self, albums, title):
        return [a for a in albums if a.get('title') == title]


class Dropbox(UploadService):
    NAME = 'dropbox'

    AUTH_URL = 'https://www.dropbox.com/oauth2/authorize'
    TOKEN_URL = 'https://api.dropboxapi.com/oauth2/token'

    CLIENT_ID = 'dropbox_client_id_placeholder'
    CLIENT_NOT_SO_SECRET = 'dropbox_client_secret_placeholder'

    LIST_FOLDER_URL = 'https://api.dropboxapi.com/2/files/list_folder'
    UPLOAD_URL = 'https://content.dropboxapi.com/2/files/upload'

    def __init__(self, camera_id):
        self._location = None
        self._authorization_key = None
        self._credentials = None

        UploadService.__init__(self, camera_id)

    @classmethod
    def get_authorize_url(cls):
        query = {
            'response_type': 'code',
            'client_id': cls.CLIENT_ID,
            'token_access_type': 'offline',
        }

        return cls.AUTH_URL + '?' + urlencode(query)

    def test_access(self):
        body = {
            'path': self._clean_location(),
            'recursive': False,
            'include_media_info': False,
            'include_deleted': False,
        }

        body = json.dumps(body)
        headers = {'Content-Type': 'application/json'}

        try:
            self._request(self.LIST_FOLDER_URL, body, headers)
            return True

        except Exception as e:
            msg = str(e)

            # remove trailing punctuation
            while msg and not msg[-1].isalnum():
                msg = msg[:-1]

            return msg

    def upload_data(self, filename, mime_type, data, ctime, camera_name):
        metadata = {
            'path': os.path.join(self._clean_location(), filename),
            'mode': 'add',
            'autorename': True,
            'mute': False,
        }

        headers = {
            'Content-Type': 'application/octet-stream',
            'Dropbox-API-Arg': json.dumps(metadata),
        }

        self._request(self.UPLOAD_URL, data, headers)

    def dump(self):
        return {
            'location': self._location,
            'credentials': self._credentials,
            'authorization_key': self._authorization_key,
        }

    def load(self, data):
        if data.get('location'):
            self._location = data['location']
        if data.get('authorization_key'):
            self._authorization_key = data['authorization_key']
            self._credentials = None
        if data.get('credentials'):
            self._credentials = data['credentials']

    def _clean_location(self):
        location = self._location
        if location == '/':
            return ''

        if not location.startswith('/'):
            location = '/' + location

        return location

    def _request(self, url, body=None, headers=None, retry_auth=True):
        if not self._credentials:
            if not self._authorization_key:
                msg = 'missing authorization key'
                self.error(msg)
                raise Exception(msg)

            self.debug('requesting credentials')
            try:
                self._credentials = self._request_credentials(self._authorization_key)
                self.save()

            except Exception as e:
                self.error(f'failed to obtain credentials: {e}')
                raise

        headers = headers or {}
        headers['Authorization'] = f'Bearer {self._credentials["access_token"]}'

        self.debug(f'requesting {url}')
        request = Request(url, data=body, headers=headers)
        try:
            response = utils.urlopen(request)

        except HTTPError as e:
            if (
                e.code == 401 and retry_auth
            ):  # unauthorized, access token may have expired
                try:
                    self.debug('credentials have probably expired, refreshing them')
                    self._credentials = self._refresh_credentials(
                        self._credentials['refresh_token']
                    )
                    self.save()

                    # retry the request with refreshed credentials
                    return self._request(url, body, headers, retry_auth=False)

                except Exception:
                    self.error('refreshing credentials failed')
                    raise

            elif str(e).count('not_found'):
                msg = f'folder "{self._location}" not found'
                self.error(msg)
                raise Exception(msg)

            else:
                self.error(f'request failed: {e}')
                raise

        except Exception as e:
            self.error(f'request failed: {e}')
            raise

        return response.read()

    def _request_credentials(self, authorization_key):
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        body = {
            'code': authorization_key,
            'client_id': self.CLIENT_ID,
            'client_secret': self.CLIENT_NOT_SO_SECRET,
            'grant_type': 'authorization_code',
        }
        body = urlencode(body).encode()

        request = Request(self.TOKEN_URL, data=body, headers=headers)

        try:
            response = utils.urlopen(request)

        except HTTPError as e:
            error = json.load(e)
            raise Exception(
                error.get('error_description') or error.get('error') or str(e)
            )

        data = json.load(response)

        return {
            'access_token': data['access_token'],
            'refresh_token': data['refresh_token'],
        }

    def _refresh_credentials(self, refresh_token):
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        body = {
            'refresh_token': refresh_token,
            'client_id': self.CLIENT_ID,
            'client_secret': self.CLIENT_NOT_SO_SECRET,
            'grant_type': 'refresh_token',
        }
        body = urlencode(body).encode()

        request = Request(self.TOKEN_URL, data=body, headers=headers)

        try:
            response = utils.urlopen(request)

        except HTTPError as e:
            error = json.load(e)
            raise Exception(
                error.get('error_description') or error.get('error') or str(e)
            )

        data = json.load(response)

        return {
            'access_token': data['access_token'],
            'refresh_token': data.get('refresh_token', refresh_token),
        }


class Webdav(UploadService):
    NAME = 'webdav'

    def __init__(self, camera_id):
        self._endpoint_url = None
        self._username = None
        self._password = None
        self._location = None

        UploadService.__init__(self, camera_id)

    def _request(self, url, method, body=None):
        base64string = b64encode(f'{self._username}:{self._password}'.encode()).decode(
            'ascii'
        )
        headers = {'Authorization': f'Basic {base64string}'}
        if body is not None:
            headers.update({'Content-Length': len(body)})
        self.debug(f'request: {method} {url}')
        request = Request(url, data=body, headers=headers)
        request.get_method = lambda: method
        try:
            utils.urlopen(request)
        except HTTPError as e:
            if method == 'MKCOL' and e.code == 405:
                self.debug(
                    'MKCOL failed with code 405, this is normal if the folder exists'
                )
            else:
                raise e

    def _make_dirs(self, path):
        dir_url = self._endpoint_url.rstrip('/') + '/'
        for folder in path.split('/'):
            dir_url = dir_url + folder + '/'
            self._request(dir_url, 'MKCOL')

    def test_access(self):
        try:
            path = self._location.strip('/') + '/' + str(time.time())
            self._make_dirs(path)
            self._request(self._endpoint_url.rstrip('/') + '/' + path, 'DELETE')
            return True
        except Exception as e:
            self.error(str(e), exc_info=True)
            return str(e)

    def upload_data(self, filename, mime_type, data, ctime, camera_name):
        path = self._location.strip('/') + '/' + os.path.dirname(filename)
        filename = os.path.basename(filename)
        self._make_dirs(path)
        self.debug(f'uploading {filename} of {len(data)} bytes')
        self._request(
            self._endpoint_url.rstrip('/') + '/' + path + '/' + filename,
            'PUT',
            bytearray(data),
        )
        self.debug('upload done')

    def dump(self):
        return {
            'endpoint_url': self._endpoint_url,
            'username': self._username,
            'password': self._password,
            'location': self._location,
        }

    def load(self, data):
        if data.get('endpoint_url') is not None:
            self._endpoint_url = data['endpoint_url']
        if data.get('username') is not None:
            self._username = data['username']
        if data.get('password') is not None:
            self._password = data['password']
        if data.get('location'):
            self._location = data['location']


class FTP(UploadService):
    NAME = 'ftp'
    CONN_LIFE_TIME = 60  # don't keep an FTP connection for more than 1 minute

    def __init__(self, camera_id):
        self._server = None
        self._port = None
        self._username = None
        self._password = None
        self._location = None

        self._conn = None
        self._conn_time = 0

        UploadService.__init__(self, camera_id)

    def test_access(self):
        try:
            conn = self._get_conn(create=True)

            path = self._make_dirs(self._location, conn=conn)
            conn.cwd(path)

            d = '%s' % int(time.time())
            self.debug(f'creating test directory {path}/{d}')
            conn.mkd(d)
            conn.rmd(d)

            return True

        except Exception as e:
            self.error(str(e), exc_info=True)

            return str(e)

    def upload_data(self, filename, mime_type, data, ctime, camera_name):
        path = os.path.dirname(filename)
        filename = os.path.basename(filename)

        conn = self._get_conn()
        path = self._make_dirs(self._location + '/' + path, conn=conn)
        conn.cwd(path)

        self.debug(f'uploading {filename} of {len(data)} bytes')
        conn.storbinary(f'STOR {filename}', io.StringIO(data))

        self.debug('upload done')

    def dump(self):
        return {
            'server': self._server,
            'port': self._port,
            'username': self._username,
            'password': self._password,
            'location': self._location,
        }

    def load(self, data):
        if data.get('server') is not None:
            self._server = data['server']
        if data.get('port') is not None:
            self._port = int(data['port'])
        if data.get('username') is not None:
            self._username = data['username']
        if data.get('password') is not None:
            self._password = data['password']
        if data.get('location'):
            self._location = data['location']

    def _get_conn(self, create=False):
        now = time.time()
        if self._conn is None or now - self._conn_time > self.CONN_LIFE_TIME or create:
            self.debug(
                'creating connection to {}@{}:{}'.format(
                    self._username or 'anonymous', self._server, self._port
                )
            )
            self._conn = ftplib.FTP()
            self._conn.set_pasv(True)
            self._conn.connect(self._server, port=self._port)
            self._conn.login(self._username or 'anonymous', self._password)
            self._conn_time = now

        return self._conn

    def _make_dirs(self, path, conn=None):
        conn = conn or self._get_conn()

        path = path.split('/')
        path = [p for p in path if p]

        self.debug('ensuring path /%s' % '/'.join(path))

        conn.cwd('/')
        for p in path:
            l = conn.nlst()
            if p not in l:
                conn.mkd(p)

            conn.cwd(p)

        return '/' + '/'.join(path)


class SFTP(UploadService):
    NAME = 'sftp'

    def __init__(self, camera_id):
        self._server = None
        self._port = None
        self._username = None
        self._password = None
        self._location = None

        UploadService.__init__(self, camera_id)

    def curl_perform_filetransfer(self, conn):
        curl_url = conn.getinfo(pycurl.EFFECTIVE_URL)

        try:
            conn.perform()

        except pycurl.error:
            curl_error = conn.errstr()
            msg = f'cURL upload failed on {curl_url}: {curl_error}'
            self.error(msg)
            raise

        else:
            self.debug(f'upload done: {curl_url}')

        finally:
            conn.close()

    def test_access(self):
        filename = time.time()
        test_folder = "motioneye_test"
        test_file = f"/{test_folder}/{filename}"

        # list of commands to send after upload.
        rm_operations = [
            f'RM {self._location}/{test_file}',
            f'RMDIR {self._location}/{test_folder}',
        ]

        conn = self._get_conn(test_file)
        conn.setopt(conn.POSTQUOTE, rm_operations)  # Executed after transfer.
        conn.setopt(pycurl.READFUNCTION, io.StringIO().read)

        try:
            self.curl_perform_filetransfer(conn)
            return True

        except Exception as e:
            logging.error(f'sftp connection failed: {e}')

            return str(e)

    def upload_data(self, filename, mime_type, data, ctime, camera_name):
        conn = self._get_conn(filename)
        conn.setopt(pycurl.READFUNCTION, io.BytesIO(data).read)

        self.curl_perform_filetransfer(conn)

    def dump(self):
        return {
            'server': self._server,
            'port': self._port,
            'username': self._username,
            'password': self._password,
            'location': self._location,
        }

    def load(self, data):
        if data.get('server') is not None:
            self._server = data['server']
        if data.get('port') is not None:
            self._port = int(data['port'])
        if data.get('username') is not None:
            self._username = data['username']
        if data.get('password') is not None:
            self._password = data['password']
        if data.get('location'):
            self._location = data['location']

    def _get_conn(self, filename, auth_type='password'):
        sftp_url = 'sftp://{}:{}/{}/{}'.format(
            self._server, self._port, self._location, filename
        )

        self.debug(
            'creating sftp connection to {}@{}:{}'.format(
                self._username, self._server, self._port
            )
        )

        self._conn = pycurl.Curl()
        self._conn.setopt(self._conn.URL, sftp_url)
        self._conn.setopt(pycurl.CONNECTTIMEOUT, 10)
        self._conn.setopt(
            self._conn.FTP_CREATE_MISSING_DIRS, 2
        )  # retry once if MKD fails

        auth_types = {
            'password': self._conn.SSH_AUTH_PASSWORD,
            # 'private_key': self._conn.SSH_PRIVATE_KEYFILE
            # ref: https://curl.haxx.se/libcurl/c/CURLOPT_SSH_PRIVATE_KEYFILE.html
        }

        try:
            self._conn.setopt(self._conn.SSH_AUTH_TYPES, auth_types[auth_type])

        except KeyError:
            self.error(f"invalid SSH auth type: {auth_type}")
            raise

        if auth_type == 'password':
            self._conn.setopt(self._conn.USERNAME, self._username)
            self._conn.setopt(self._conn.PASSWORD, self._password)

        self._conn.setopt(self._conn.UPLOAD, 1)

        return self._conn


class S3(UploadService):
    NAME = 's3'

    def __init__(self, camera_id):
        self._endpoint_url = None
        self._access_key = None
        self._secret_key = None
        self._bucket = None
        UploadService.__init__(self, camera_id)

    @classmethod
    def dump(self):
        return {
            'endpoint_url': self._endpoint_url,
            'access_key': self._access_key,
            'secret_key': self._secret_key,
            'bucket': self._bucket,
        }

    def load(self, data):
        if data.get('endpoint_url'):
            self._endpoint_url = data['endpoint_url']
        if data.get('access_key') is not None:
            self._access_key = data['access_key']
        if data.get('secret_key') is not None:
            self._secret_key = data['secret_key']
        if data.get('bucket') is not None:
            self._bucket = data['bucket']

    def upload_file(self, target_dir, filename, camera_name):
        # Create an S3 client
        s3 = boto3.client(
            's3',
            endpoint_url=self._endpoint_url,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
        )

        # Uploads the given file using a managed uploader, which will split up
        # large files automatically and upload parts in parallel.
        self.debug(f'uploading file "{filename}" to S3 bucket "{self._bucket}"')
        s3.upload_file(filename, self._bucket, filename[len(target_dir) :])

    def test_access(self):
        try:
            # Create an S3 client
            s3 = boto3.client(
                's3',
                endpoint_url=self._endpoint_url,
                aws_access_key_id=self._access_key,
                aws_secret_access_key=self._secret_key,
            )
            response = s3.list_buckets()
            logging.debug('Existing buckets:')
            for bucket in response['Buckets']:
                logging.debug(f'  {bucket["Name"]}')
            return True
        except Exception as e:
            logging.error(f'S3 connection failed: {e}')
            return str(e)


def get_authorize_url(service_name):
    cls = UploadService.get_service_classes().get(service_name)

    if cls:
        return cls.get_authorize_url()

    else:
        return None


def get(camera_id, service_name):
    global _services

    if _services is None:
        _services = _load()

    camera_id = str(camera_id)

    service = _services.get(camera_id, {}).get(service_name)

    if service is None:
        cls = UploadService.get_service_classes().get(service_name)

        if cls:
            service = cls(camera_id=camera_id)
            _services.setdefault(camera_id, {})[service_name] = service

            logging.debug(
                f'created default upload service "{service_name}" for camera with id "{camera_id}"'
            )

    return service


def test_access(camera_id, service_name, data):
    logging.debug(f'testing access to {service_name}')

    service = get(camera_id, service_name)
    service.load(data)
    if not service:
        return f'unknown upload service {service_name}'

    return service.test_access()


def update(camera_id, service_name, settings):
    service = get(camera_id, service_name)
    service.load(settings)
    service.save()


def upload_media_file(camera_id, camera_name, target_dir, service_name, filename):
    service = get(camera_id, service_name)
    if not service:
        return logging.error(
            f'service "{service_name}" not initialized for camera with id {camera_id}'
        )

    try:
        service.upload_file(target_dir, filename, camera_name)

    except Exception as e:
        logging.error(
            f'failed to upload file "{filename}" with service {service}: {e}',
            exc_info=True,
        )


def _load():
    services = {}

    file_path = os.path.join(settings.CONF_PATH, _STATE_FILE_NAME)

    if os.path.exists(file_path):
        logging.debug(f'loading upload services state from "{file_path}"...')

        try:
            f = open(file_path)

        except Exception as e:
            logging.error(
                f'could not open upload services state file "{file_path}": {e}'
            )

            return services

        try:
            data = json.load(f)

        except Exception as e:
            logging.error(
                f'could not read upload services state from file "{file_path}": {e}'
            )

            return services

        finally:
            f.close()

        for camera_id, d in list(data.items()):
            for name, state in list(d.items()):
                camera_services = services.setdefault(camera_id, {})
                cls = UploadService.get_service_classes().get(name)

                if cls:
                    service = cls(camera_id=camera_id)
                    service.load(state)

                    camera_services[name] = service

                    logging.debug(
                        f'loaded upload service "{name}" for camera with id "{camera_id}"'
                    )

    return services


def _save(services):
    file_path = os.path.join(settings.CONF_PATH, _STATE_FILE_NAME)

    logging.debug(f'saving upload services state to "{file_path}"...')

    data = {}
    for camera_id, camera_services in list(services.items()):
        for name, service in list(camera_services.items()):
            data.setdefault(str(camera_id), {})[name] = service.dump()

    try:
        f = open(file_path, 'w')

    except Exception as e:
        logging.error(f'could not open upload services state file "{file_path}": {e}')

        return

    try:
        json.dump(data, f, sort_keys=True, indent=4)

    except Exception as e:
        logging.error(
            f'could not save upload services state to file "{file_path}": {e}'
        )

    finally:
        f.close()


def clean_cloud(local_dir, data, info):
    camera_id = info['camera_id']
    service_name = info['service_name']
    cloud_dir_user = info['cloud_dir']
    cloud_dir = [p.strip() for p in cloud_dir_user.split('/') if p.strip()][0]

    logging.debug(f'clean_cloud({camera_id}, {service_name}, {local_dir}, {cloud_dir})')

    if service_name and local_dir and cloud_dir:
        local_folders = get_local_folders(local_dir)
        service = get(camera_id, service_name)
        service.load(data)
        service.clean_cloud(cloud_dir, local_folders)


def exist_in_local(folder, local_folders):
    if not local_folders:
        local_folders = []

    if not folder:
        return False

    return folder in local_folders


def get_local_folders(dirpath):
    folders = next(os.walk(dirpath))[1]
    return folders
