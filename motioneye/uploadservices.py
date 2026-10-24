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
from __future__ import annotations

import json
import logging
import os.path
import ssl
from abc import ABC, abstractmethod
from base64 import b64decode, b64encode
from datetime import datetime
from ftplib import FTP as FTPc  # nosec: B402
from ftplib import FTP_TLS as FTPTLSc  # nosec: B402
from hashlib import md5
from inspect import isabstract
from io import BytesIO, StringIO
from mimetypes import guess_type
from os import stat
from stat import S_IMODE
from time import time
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request

import boto3
import pycurl

from motioneye import settings, utils

_STATE_FILE_NAME: str = 'uploadservices.json'
_services: dict | None = None


class UploadService(ABC):
    NAME: str
    MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1GB

    def __init__(self, camera_id: str, **kwargs) -> None:
        self.camera_id = camera_id

    def __str__(self) -> str:
        return self.NAME

    @classmethod
    def get_authorize_url(cls) -> str:
        return '/'

    @abstractmethod
    def test_access(self) -> bool | str: ...

    def upload_file(
        self, target_dir: str | None, filename: str, camera_name: str
    ) -> None:
        ctime = os.path.getctime(filename)

        if target_dir:
            target_dir = os.path.realpath(target_dir)
            rel_filename = os.path.realpath(filename)
            rel_filename = rel_filename[len(target_dir) :].lstrip('/')

            self.debug(f'uploading file "{target_dir}/{rel_filename}" to {self}')

        else:
            rel_filename = os.path.basename(filename)

            self.debug(f'uploading file "{filename}" to {self}')

        try:
            st = os.stat(filename)

        except Exception as e:
            msg = f'failed to open file "{filename}": {e}'
            self.error(msg)
            raise RuntimeError(msg)

        if st.st_size > self.MAX_FILE_SIZE:
            msg = f'file "{filename}" is too large ({st.st_size / 1024 / 1024}MB/{self.MAX_FILE_SIZE / 1024 / 1024}MB)'
            self.error(msg)
            raise RuntimeError(msg)

        try:
            with open(filename, 'rb') as f:
                data = f.read()

        except Exception as e:
            msg = f'failed to read file "{filename}": {e}'
            self.error(msg)
            raise RuntimeError(msg)

        self.debug(f'size of "{filename}" is {len(data) / 1024.0 / 1024:.3f}MB')

        mime_type = guess_type(filename)[0] or 'image/jpeg'
        self.debug(f'mime type of "{filename}" is "{mime_type}"')

        self.upload_data(rel_filename, mime_type, data, ctime, camera_name)

        self.debug(f'file "{filename}" successfully uploaded')

    def upload_data(self, filename, mime_type, data, ctime, camera_name):
        pass

    @abstractmethod
    def dump(self) -> dict: ...

    @abstractmethod
    def load(self, data: dict) -> None: ...

    def save(self) -> None:
        services: dict[str, dict[str, UploadService]] = _load()
        camera_services = services.setdefault(self.camera_id, {})
        camera_services[self.NAME] = self

        _save(services)

    def log(self, level, message: str, **kwargs) -> None:
        message = self.NAME + ': ' + message
        logging.log(level, message, **kwargs)

    def debug(self, message: str, **kwargs) -> None:
        self.log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        self.log(logging.INFO, message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        self.log(logging.ERROR, message, **kwargs)

    def clean_cloud(self, cloud_dir: str, local_folders: list):
        pass


class GoogleBase(UploadService, ABC):
    SCOPE: str
    AUTH_URL: str = 'https://accounts.google.com/o/oauth2/auth'
    TOKEN_URL: str = 'https://accounts.google.com/o/oauth2/token'
    CLIENT_ID: str = (
        '349038943026-m16svdadjrqc0c449u4qv71v1m1niu5o.apps.googleusercontent.com'
    )
    CLIENT_NOT_SO_SECRET: str = 'jjqbWmICpA0GvbhsJB3okX7s'

    def __init__(self, camera_id: str) -> None:
        self._location: str | None = None
        self._authorization_key: str | None = None
        self._credentials: dict | None = None
        self._folder_ids: dict[str, str] = {}
        self._folder_id_times: dict[str, float] = {}
        super().__init__(camera_id)

    @classmethod
    def get_authorize_url(cls) -> str:
        query = {
            'scope': cls.SCOPE,
            'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
            'response_type': 'code',
            'client_id': cls.CLIENT_ID,
            'access_type': 'offline',
        }

        return cls.AUTH_URL + '?' + urlencode(query)

    def test_access(self) -> bool | str:
        try:
            self._folder_ids = {}
            self._get_folder_id()
            return True

        except Exception as e:
            return str(e)

    def dump(self) -> dict:
        return {
            'location': self._location,
            'credentials': self._credentials,
            'authorization_key': self._authorization_key,
        }

    def load(self, data: dict) -> None:
        if data.get('location'):
            self._location = data['location']
            self._folder_ids = {}
        if data.get('authorization_key'):
            self._authorization_key = data['authorization_key']
            self._credentials = None
        if data.get('credentials'):
            self._credentials = data['credentials']

    @abstractmethod
    def _get_folder_id(self, path: str = '') -> str: ...

    def _request(self, url: str, body=None, headers=None, retry_auth=True, method=None):
        if not self._credentials:
            if not self._authorization_key:
                msg = 'missing authorization key'
                self.error(msg)
                raise ValueError(msg)

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
        request = Request(url, data=body, headers=headers, method=method)
        try:
            response = utils.urlopen(request)

        except HTTPError as e:
            # unauthorized, access token may have expired
            if e.code == 401 and retry_auth:
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
                raise RuntimeError(msg)

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
            raise RuntimeError(
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
            raise RuntimeError(
                error.get('error_description') or error.get('error') or str(e)
            )

        data = json.load(response)

        return {
            'access_token': data['access_token'],
            'refresh_token': data.get('refresh_token', refresh_token),
        }


class GoogleDrive(GoogleBase):
    NAME: str = 'gdrive'
    SCOPE: str = 'https://www.googleapis.com/auth/drive.file'
    CHILDREN_URL: str = (
        'https://www.googleapis.com/drive/v2/files/%(parent_id)s/children?q=%(query)s'
    )
    CHILDREN_QUERY: str = (
        "'%(parent_id)s' in parents and title = '%(child_name)s' and trashed = false"
    )
    UPLOAD_URL: str = (
        'https://www.googleapis.com/upload/drive/v2/files?uploadType=multipart'
    )
    CREATE_FOLDER_URL: str = 'https://www.googleapis.com/drive/v2/files'
    BOUNDARY: str = 'motioneye_multipart_boundary'
    FOLDER_ID_LIFE_TIME: int = 300  # 5 minutes

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

        body = '\r\n'.join(body).encode()
        body += data
        body += f'\r\n--{self.BOUNDARY}--'.encode()

        headers = {
            'Content-Type': f'multipart/related; boundary="{self.BOUNDARY}"',
            'Content-Length': len(body),
        }

        self._request(self.UPLOAD_URL, body, headers)

    def _get_folder_id(self, path: str = '') -> str:
        now: float = time()
        folder_id: str = self._folder_ids.get(path, '')
        folder_id_time: float = self._folder_id_times.get(path, 0)

        if not folder_id or (now - folder_id_time > self.FOLDER_ID_LIFE_TIME):
            location: str = self._location or '/'
            if path:
                if not location.endswith('/'):
                    location += '/'

                location += path

            self.debug(f'finding folder id for location "{location}"')
            folder_id = self._get_folder_id_by_path(location)

            self._folder_ids[path] = folder_id
            self._folder_id_times[path] = now

        return folder_id

    def _get_folder_id_by_path(self, path: str) -> str:
        if path != '/':
            paths: list[str] = [p.strip() for p in path.split('/') if p.strip()]
            parent_id: str = 'root'
            for name in paths:
                parent_id = self._get_folder_id_by_name(parent_id, name)

            return parent_id

        else:  # root folder
            return self._get_folder_id_by_name(None, 'root')

    def _get_folder_id_by_name(
        self, parent_id: str | None, child_name: str, create: bool | None = True
    ) -> str:
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
                raise RuntimeError(msg)

        return items[0]['id']

    def _create_folder(self, parent_id: str, child_name: str):
        metadata = {
            'title': child_name,
            'parents': [{'id': parent_id}],
            'mimeType': 'application/vnd.google-apps.folder',
        }

        body = json.dumps(metadata).encode()

        headers = {'Content-Type': 'application/json; charset=UTF-8'}

        self._request(self.CREATE_FOLDER_URL, body, headers)

    def clean_cloud(self, cloud_dir: str, local_folders: list) -> int:
        # remove old cloud folder that does not exist in local.
        # assumes 'cloud_dir' is a direct child of the 'root'.

        removed_count: int = 0
        folder_id = self._get_folder_id_by_name('root', cloud_dir, False)
        children: list = self._get_children(folder_id)
        self.info(
            f'found {len(local_folders)}/{len(children)} folder(s) in local/cloud'
        )
        self.debug(f'local {local_folders}')
        for child in children:
            id = child['id']
            name = self._get_file_metadata(id)['title']
            self.debug(f"cloud '{name}'")
            to_delete = not name in local_folders
            if to_delete and self._delete_file(id):
                removed_count += 1
                self.info(f"deleted a cloud folder '{name}'")

        self.info(f'deleted {removed_count} cloud folder(s)')
        return removed_count

    def _get_children(self, file_id) -> list:
        url = f'{self.CREATE_FOLDER_URL}/{file_id}/children'
        response = self._request(url)

        try:
            response = json.loads(response)

        except Exception:
            self.error("response doesn't seem to be a valid json")
            raise

        return response['items']

    def _delete_file(self, file_id) -> bool:
        url = f'{self.CREATE_FOLDER_URL}/{file_id}'
        response = self._request(url, None, None, True, 'DELETE')
        return response == ''

    def _get_file_metadata(self, file_id) -> dict:
        url = f'{self.CREATE_FOLDER_URL}/{file_id}'
        response = self._request(url)

        try:
            response = json.loads(response)

        except Exception:
            self.error("response doesn't seem to be a valid json")
            raise

        return response


class GooglePhoto(GoogleBase):
    NAME: str = 'gphoto'
    SCOPE: str = 'https://www.googleapis.com/auth/photoslibrary'
    GOOGLE_PHOTO_API: str = 'https://photoslibrary.googleapis.com/v1/'

    def upload_data(self, filename, mime_type, data, ctime, camera_name):
        filename = os.path.basename(filename)
        dayinfo = datetime.fromtimestamp(ctime).strftime('%Y-%m-%d')
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

    def _get_folder_id(self, path: str = '') -> str:
        location: str = self._location or ''
        folder_id: str = self._folder_ids.get(location, '')

        self.debug(f'_get_folder_id({path}, {location}, {folder_id})')

        if not folder_id:
            self.debug(f'finding album with title "{location}"')
            folder_id = self._get_folder_id_by_name(location)

            self._folder_ids[location] = folder_id

        return folder_id

    def _get_folder_id_by_name(self, name: str, create: bool = True) -> str:
        try:
            albums: list = self._get_albums()
            albumsWithName: list = self._filter_albums(albums, name)

            if albumsWithName:
                count = len(albumsWithName)
                if count > 0:
                    albumId = albumsWithName[0].get('id')
                    self.debug(
                        f'found {count} existing album(s) "{name}" taking first id "{albumId}"'
                    )
                    return albumId

            # create album
            response: dict = self._create_folder(name)
            albumId = response.get('id') or ''
            self.info(f'Album "{name}" was created successfully with id "{albumId}"')
            return albumId

        except Exception as e:
            self.error(f"_get_folder_id_by_name() failed: {e}")
            raise

    def _create_folder(self, child_name: str) -> dict:
        metadata = {'album': {'title': child_name}}

        body = json.dumps(metadata)

        headers = {'Content-Type': 'application/json'}

        response: dict = self._request_json(
            self.GOOGLE_PHOTO_API + 'albums', body, headers
        )
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

    def _get_albums(self) -> list:
        response: dict = self._request_json(self.GOOGLE_PHOTO_API + 'albums')

        albums: list = response.get('albums') or []
        self.debug(f'got {len(albums)} album(s)')
        return albums

    def _filter_albums(self, albums: list, title: str) -> list:
        return [a for a in albums if a.get('title') == title]


class Dropbox(UploadService):
    NAME = 'dropbox'
    AUTH_URL = 'https://www.dropbox.com/oauth2/authorize'
    TOKEN_URL = 'https://api.dropboxapi.com/oauth2/token'
    CLIENT_ID = 'dropbox_client_id_placeholder'
    CLIENT_NOT_SO_SECRET = 'dropbox_client_secret_placeholder'
    LIST_FOLDER_URL = 'https://api.dropboxapi.com/2/files/list_folder'
    UPLOAD_URL = 'https://content.dropboxapi.com/2/files/upload'

    def __init__(self, camera_id: str) -> None:
        self._location: str | None = None
        self._authorization_key: str | None = None
        self._credentials: dict | None = None
        super().__init__(camera_id)

    @classmethod
    def get_authorize_url(cls) -> str:
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

        # the body must be bytes: urllib's Request rejects a str POST body
        # with "POST data should be bytes ... not str" (#2828)
        body = json.dumps(body).encode()
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

    def dump(self) -> dict:
        return {
            'location': self._location,
            'credentials': self._credentials,
            'authorization_key': self._authorization_key,
        }

    def load(self, data: dict) -> None:
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
                raise ValueError(msg)

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
                raise FileNotFoundError(msg)

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
            raise RuntimeError(
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
            raise RuntimeError(
                error.get('error_description') or error.get('error') or str(e)
            )

        data = json.load(response)

        return {
            'access_token': data['access_token'],
            'refresh_token': data.get('refresh_token', refresh_token),
        }


class Webdav(UploadService):
    NAME = 'webdav'

    def __init__(self, camera_id: str) -> None:
        self._endpoint_url: str | None = None
        self._username: str | None = None
        self._password: str | None = None
        self._location: str | None = None
        super().__init__(camera_id)

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
                raise

    def _make_dirs(self, path):
        dir_url = self._endpoint_url.rstrip('/') + '/'
        for folder in path.split('/'):
            dir_url = dir_url + folder + '/'
            self._request(dir_url, 'MKCOL')

    def test_access(self):
        try:
            path = self._location.strip('/') + '/' + str(time())
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

    def dump(self) -> dict:
        return {
            'endpoint_url': self._endpoint_url,
            'username': self._username,
            'password': self._password,
            'location': self._location,
        }

    def load(self, data: dict) -> None:
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

    def __init__(self, camera_id: str) -> None:
        self._server: str | None = None
        self._port: int | None = None
        self._username: str | None = None
        self._password: str | None = None
        self._location: str | None = None
        self._conn = None
        self._conn_time: float | None = 0
        super().__init__(camera_id)

    def test_access(self):
        try:
            conn = self._get_conn(create=True)

            path = self._make_dirs(self._location, conn=conn)
            conn.cwd(path)

            d = f'{int(time())}'
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
        conn.storbinary(f'STOR {filename}', BytesIO(data))

        self.debug('upload done')

    def dump(self) -> dict:
        return {
            'server': self._server,
            'port': self._port,
            'username': self._username,
            'password': self._password,
            'location': self._location,
        }

    def load(self, data: dict) -> None:
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
        now = time()
        if self._conn is None or now - self._conn_time > self.CONN_LIFE_TIME or create:
            self.debug(
                'creating connection to {}@{}:{}'.format(
                    self._username or 'anonymous', self._server, self._port
                )
            )
            self._conn = FTPc()  # nosec: B321
            self._conn.set_pasv(True)
            self._conn.connect(self._server, port=self._port)
            self._conn.login(self._username or 'anonymous', self._password)
            self._conn_time = now

        return self._conn

    def _make_dirs(self, path, conn=None):
        conn = conn or self._get_conn()

        path = path.split('/')
        path = [p for p in path if p]

        self.debug(f'ensuring path /{"/".join(path)}')

        conn.cwd('/')
        for p in path:
            ls = conn.nlst()
            if p not in ls:
                conn.mkd(p)

            conn.cwd(p)

        return '/' + '/'.join(path)


class _FTPTLSSessionReuse(FTPTLSc):
    """FTP_TLS that resumes the control connection's TLS session on the data
    connections. vsftpd, ProFTPD and FileZilla Server require that by default
    and refuse the transfer otherwise; ftplib does not do it (python/cpython#63699)."""

    def ntransfercmd(self, cmd, rest=None):
        conn, size = FTPc.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            conn = self.context.wrap_socket(
                conn, server_hostname=self.host, session=self.sock.session
            )

        return conn, size


class FTPS(FTP):
    NAME = 'ftps'
    # seconds; without a timeout a server that never answers hangs the "Test" button
    SOCKET_TIMEOUT = 30

    def __init__(self, camera_id: str) -> None:
        self._verify: bool = True
        super().__init__(camera_id)

    def dump(self) -> dict:
        data = super().dump()
        data['verify'] = self._verify

        return data

    def load(self, data: dict) -> None:
        super().load(data)
        verify = data.get('verify')
        if isinstance(verify, str):
            verify = verify.lower() in ('true', 'on', '1', 'yes')
        if verify is not None:
            self._verify = bool(verify)

    def _get_conn(self, create=False):
        now = time()
        if self._conn is None or now - self._conn_time > self.CONN_LIFE_TIME or create:
            self.debug(
                'creating TLS connection to {}@{}:{} (certificate check {})'.format(
                    self._username or 'anonymous',
                    self._server,
                    self._port,
                    'on' if self._verify else 'off',
                )
            )
            context = ssl.create_default_context()
            if not self._verify:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            self._conn = _FTPTLSSessionReuse(
                context=context, timeout=self.SOCKET_TIMEOUT
            )
            self._conn.set_pasv(True)
            self._conn.connect(self._server, port=self._port)
            self._conn.login(self._username or 'anonymous', self._password)
            self._conn.prot_p()
            self._conn_time = now

        return self._conn


class SFTP(UploadService):
    NAME = 'sftp'

    def __init__(self, camera_id: str) -> None:
        self._server: str | None = None
        self._port: int | None = None
        self._username: str | None = None
        self._password: str | None = None
        self._location: str | None = None
        super().__init__(camera_id)

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
        filename = time()
        test_folder = "motioneye_test"
        test_file = f"/{test_folder}/{filename}"

        # list of commands to send after upload.
        rm_operations = [
            f'RM {self._location}/{test_file}',
            f'RMDIR {self._location}/{test_folder}',
        ]

        conn = self._get_conn(test_file)
        conn.setopt(conn.POSTQUOTE, rm_operations)  # Executed after transfer.
        conn.setopt(pycurl.READFUNCTION, StringIO().read)

        try:
            self.curl_perform_filetransfer(conn)
            return True

        except Exception as e:
            logging.error(f'sftp connection failed: {e}')

            return str(e)

    def upload_data(self, filename, mime_type, data, ctime, camera_name):
        conn = self._get_conn(filename)
        conn.setopt(pycurl.READFUNCTION, BytesIO(data).read)

        self.curl_perform_filetransfer(conn)

    def dump(self) -> dict:
        return {
            'server': self._server,
            'port': self._port,
            'username': self._username,
            'password': self._password,
            'location': self._location,
        }

    def load(self, data: dict) -> None:
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
        sftp_url = f'sftp://{self._server}:{self._port}/{self._location}/{filename}'

        self.debug(
            f'creating sftp connection to {self._username}@{self._server}:{self._port}'
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

    def __init__(self, camera_id: str) -> None:
        self._endpoint_url: str | None = None
        self._access_key: str | None = None
        self._secret_key: str | None = None
        self._bucket: str | None = None
        self._sse_c_key: str | None = None
        super().__init__(camera_id)

    def dump(self) -> dict:
        return {
            'endpoint_url': self._endpoint_url,
            'access_key': self._access_key,
            'secret_key': self._secret_key,
            'bucket': self._bucket,
            'sse_c_key': self._sse_c_key,
        }

    def load(self, data: dict) -> None:
        if data.get('endpoint_url'):
            self._endpoint_url = data['endpoint_url']
        if data.get('access_key') is not None:
            self._access_key = data['access_key']
        if data.get('secret_key') is not None:
            self._secret_key = data['secret_key']
        if data.get('bucket') is not None:
            self._bucket = data['bucket']
        if data.get('sse_c_key') is not None:
            self._sse_c_key = data['sse_c_key']

    def upload_file(
        self, target_dir: str | None, filename: str, camera_name: str
    ) -> None:
        # Create an S3 client
        s3 = boto3.client(
            's3',
            endpoint_url=self._endpoint_url,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
        )

        if target_dir:
            target_dir = os.path.realpath(target_dir)
            rel_filename = os.path.realpath(filename)
            rel_filename = rel_filename[len(target_dir) :].lstrip('/')

        else:
            rel_filename = os.path.basename(filename)

        if self._sse_c_key:
            sse_key_md5 = b64encode(
                md5(b64decode(self._sse_c_key)).digest()  # nosec: B324
            ).decode()
            extra_args = {
                'SSECustomerAlgorithm': 'AES256',
                'SSECustomerKey': self._sse_c_key,
                'SSECustomerKeyMD5': sse_key_md5,
            }
        else:
            extra_args = None

        # Uploads the given file using a managed uploader, which will split up
        # large files automatically and upload parts in parallel.
        self.debug(
            f'uploading file "{filename}" to S3 bucket "{self._bucket}" path "{rel_filename}"'
        )
        s3.upload_file(filename, self._bucket, rel_filename, ExtraArgs=extra_args)

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


def _get_service_classes(
    cls: type[UploadService] = UploadService,
) -> dict[str, type[UploadService]]:
    services: dict[str, type[UploadService]] = {}

    for c in cls.__subclasses__():
        # Loop recursively through subclasses
        services.update(_get_service_classes(c))

        # exclude abstract classes, i.e. such with at least one @abstractmethod
        if not isabstract(c):
            services[c.NAME] = c

    return services


def get_authorize_url(service_name: str) -> str | None:
    cls: type[UploadService] | None = _get_service_classes().get(service_name)
    if cls is None:
        return None

    return cls.get_authorize_url()


def _get_service(camera_id: int, service_name: str) -> UploadService | None:
    global _services
    if _services is None:
        _services = _load()

    camera_id_str: str = str(camera_id)

    service: UploadService | None = _services.get(camera_id_str, {}).get(service_name)

    if service is None:
        cls: type[UploadService] | None = _get_service_classes().get(service_name)

        if cls is not None:
            service = cls(camera_id=camera_id_str)
            _services.setdefault(camera_id_str, {})[service_name] = service

            logging.debug(
                f'created default upload service "{service_name}" for camera with id "{camera_id_str}"'
            )

    return service


def test_access(camera_id: int, service_name: str, data: dict) -> bool | str:
    logging.debug(f'testing access to {service_name}')

    cls: type[UploadService] | None = _get_service_classes().get(service_name)
    if cls is None:
        return f'unknown upload service {service_name}'

    service: UploadService = cls(camera_id=str(camera_id))
    service.load(data)
    return service.test_access()


def update(camera_id: int, service_name: str, settings: dict) -> None:
    service: UploadService | None = _get_service(camera_id, service_name)
    if service is None:
        raise ValueError(f'unknown upload service {service_name}')

    service.load(settings)
    service.save()


def upload_media_file(
    camera_id: int,
    camera_name: str,
    target_dir: str,
    service_name: str,
    filename: str,
    clean_uploaded: bool = False,
) -> None:
    service: UploadService | None = _get_service(camera_id, service_name)
    if service is None:
        logging.error(
            f'service "{service_name}" not initialized for camera with id {camera_id}'
        )
        return

    try:
        service.upload_file(target_dir, filename, camera_name)

    except Exception:
        logging.exception(f'failed to upload file "{filename}" with service {service}')
        return  # upload failed: keep the local file

    # the caller passes clean_uploaded so we can skip the camera config lookup
    # and the mediafiles import entirely on the common path (feature disabled)
    if not clean_uploaded:
        return

    # upload succeeded and the camera removes its local copy after upload
    try:
        # local imports to avoid the config/mediafiles <-> uploadservices
        # circular imports (both modules import uploadservices at module level)
        from motioneye.config import get_camera
        from motioneye.mediafiles import del_media_content

        camera_config = get_camera(camera_id)
        rel = filename.removeprefix(camera_config['target_dir'] + os.sep)
        del_media_content(camera_config, rel)
        logging.debug(f'removed local file "{filename}" after successful upload')

    except Exception:
        # never let a cleanup error affect the (already successful) upload
        logging.exception(f'failed to remove local file "{filename}" after upload')


def _load() -> dict[str, dict[str, UploadService]]:
    services: dict[str, dict[str, UploadService]] = {}
    file_path: str = os.path.join(settings.CONF_PATH, _STATE_FILE_NAME)

    if not os.path.exists(file_path):
        return {}

    logging.debug(f'loading upload services state from "{file_path}" ...')

    try:
        f = open(file_path)  # noqa: SIM115

    except Exception as e:
        logging.error(f'could not open upload services state file "{file_path}": {e}')
        return {}

    with f:
        if S_IMODE(stat(file_path).st_mode) != 0o600:
            logging.warning(
                f'upload services state file "{file_path}" has insecure mode, applying 0600 ...'
            )
            try:
                os.chmod(file_path, 0o600)

            except Exception as e:
                logging.error(
                    f'could not harden mode of upload services state file "{file_path}": {e}'
                )
                raise

        try:
            data = json.load(f)

        except Exception as e:
            logging.error(
                f'could not parse upload services state from file "{file_path}": {e}'
            )
            return {}

        service_classes: dict[str, type[UploadService]] = _get_service_classes()

        for camera_id, d in list(data.items()):
            for name, state in list(d.items()):
                cls = service_classes.get(name)
                if cls is None:
                    logging.warning(f'unknown upload service {name!r} in {file_path!r}')
                    continue

                service: UploadService = cls(camera_id=camera_id)
                service.load(state)

                camera_services: dict[str, UploadService] = services.setdefault(
                    camera_id, {}
                )
                camera_services[name] = service
                logging.debug(
                    f'loaded upload service "{name}" for camera with id "{camera_id}"'
                )

    return services


def _save(services: dict[str, dict[str, UploadService]]) -> None:
    file_path: str = os.path.join(settings.CONF_PATH, _STATE_FILE_NAME)

    logging.debug(f'saving upload services state to "{file_path}" ...')

    data: dict[str, dict[str, dict]] = {}
    for camera_id, camera_services in list(services.items()):
        for name, service in list(camera_services.items()):
            data.setdefault(str(camera_id), {})[name] = service.dump()

    try:
        fd = os.open(
            file_path,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            0o600,
        )

    except Exception as e:
        logging.error(
            f'could not open upload services state file "{file_path}" for writing: {e}'
        )
        raise

    try:
        f = os.fdopen(fd, 'w')

    except Exception as e:
        os.close(fd)
        logging.error(
            f'could not open descriptor of upload services state file "{file_path}" for writing: {e}'
        )
        raise

    with f:
        try:
            json.dump(data, f, sort_keys=True, indent=4)

        except Exception as e:
            logging.error(
                f'could not write upload services state to file "{file_path}": {e}'
            )


def clean_cloud(local_dir: str, data: dict, info: dict) -> None:
    camera_id: int = info['camera_id']
    service_name: str = info['service_name']
    cloud_dir_user: str = info['cloud_dir']
    cloud_dir: str = next(p.strip() for p in cloud_dir_user.split('/') if p.strip())

    logging.debug(f'clean_cloud({camera_id}, {service_name}, {local_dir}, {cloud_dir})')

    if service_name and local_dir and cloud_dir:
        local_folders: list = next(os.walk(local_dir))[1]
        service: UploadService | None = _get_service(camera_id, service_name)
        if service is None:
            logging.error(
                f'service "{service_name}" not initialized for camera with id {camera_id}'
            )
            return

        service.load(data)
        service.clean_cloud(cloud_dir, local_folders)
