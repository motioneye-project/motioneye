
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

import httplib2
import json
import logging
import mimetypes
import os.path
import urllib
import urllib2 

from oauth2client.client import OAuth2WebServerFlow, Credentials

import settings


_STATE_FILE_NAME = 'uploadservices.json'

_services = {}


class UploadService(object):
    NAME = 'base'

    def __init__(self, **kwargs):
        pass

    def __str__(self):
        return self.NAME
    
    def get_authorize_url(self):
        return '/'
    
    def test_access(self):
        return True

    def upload_file(self, filename):
        self.debug('uploading file "%s" to %s' % (filename, self))
        
        try:
            st = os.stat(filename)
        
        except Exception as e:
            msg = 'failed to open file "%s": %s' % (filename, e)
            self.error(msg)
            raise Exception(msg)
         
        if st.st_size > self.MAX_FILE_SIZE:
            msg = 'file "%s" is too large (%sMB/%sMB)' % (filename, st.st_size / 1024 / 1024, self.MAX_FILE_SIZE / 1024 / 1024)
            self.error(msg)
            raise Exception(msg)

        try:
            f = open(filename)
            
        except Exception as e:
            msg = 'failed to open file "%s": %s' % (filename, e)
            self.error(msg)
            raise Exception(msg)

        data = f.read()
        self.debug('size of "%s" is %.1fMB' % (filename, len(data) / 1024.0 / 1024))
        
        mime_type = mimetypes.guess_type(filename)[0] or 'image/jpeg'
        self.debug('mime type of "%s" is "%s"' % (filename, mime_type))

        self.upload_data(filename, mime_type, data)

    def upload_data(self, filename, mime_type, data):
        pass
    
    def dump(self):
        return {}
    
    def load(self, data):
        pass

    def log(self, level, *args, **kwargs):
        logging.log(level, *args, **kwargs)

    def debug(self, *args, **kwargs):
        self.log(logging.DEBUG, *args, **kwargs)

    def info(self, *args, **kwargs):
        self.log(logging.INFO, *args, **kwargs)

    def error(self, *args, **kwargs):
        self.log(logging.ERROR, *args, **kwargs)
        
    @staticmethod
    def get_service_classes():
        return {c.NAME: c for c in UploadService.__subclasses__()}


class GoogleDrive(UploadService):
    NAME = 'gdrive'
    CLIENT_ID = '349038943026-m16svdadjrqc0c449u4qv71v1m1niu5o.apps.googleusercontent.com'
    CLIENT_NOT_SO_SECRET = 'jjqbWmICpA0GvbhsJB3okX7s'
    SCOPE = 'https://www.googleapis.com/auth/drive'
    CHILDREN_URL = 'https://www.googleapis.com/drive/v2/files/%(parent_id)s/children?q=%(query)s'
    CHILDREN_QUERY = "'%(parent_id)s' in parents and title = '%(child_name)s'"
    UPLOAD_URL = 'https://www.googleapis.com/upload/drive/v2/files?uploadType=multipart'
    BOUNDARY = 'motioneye_multipart_boundary'
    MAX_FILE_SIZE = 128 * 1024 * 1024 # 128 MB

    def __init__(self, location=None, authorization_key=None, credentials=None, **kwargs):
        self._location = location
        self._authorization_key = authorization_key
        self._credentials = credentials
        self._folder_id = None

    def get_authorize_url(self):
        flow = OAuth2WebServerFlow(client_id=self.CLIENT_ID, client_secret=self.CLIENT_NOT_SO_SECRET,
                scope='https://www.googleapis.com/auth/drive', redirect_uri='urn:ietf:wg:oauth:2.0:oob')

        return flow.step1_get_authorize_url()

    def test_access(self):
        try:
            self._folder_id = None
            self._get_folder_id()
            return True

        except Exception as e:
            return str(e)

    def upload_data(self, filename, mime_type, data):
        metadata = {
            'title': filename,
            'parents': [{'id': self._get_folder_id()}]
        }

        body = ['--' + self.BOUNDARY]
        body.append('Content-Type: application/json; charset=UTF-8')
        body.append('')
        body.append(json.dumps(metadata))
        body.append('')
        
        body.append('--' + self.BOUNDARY)
        body.append('Content-Type: %s' % mime_type)
        body.append('')
        body.append('')
        body = '\r\n'.join(body)
        body += data
        body += '\r\n--%s--' % self.BOUNDARY
        
        headers = {
            'Content-Type': 'multipart/related; boundary="%s"' % self.BOUNDARY,
            'Content-Length': len(body)
        }
        
        self._request(self.UPLOAD_URL, body, headers)

    def dump(self):
        return {
            'location': self._location,
            'credentials': self._credentials and json.loads(self._credentials.to_json()),
            'authorization_key': self._authorization_key,
            'folder_id': self._folder_id
        }

    def load(self, data):
        if 'location' in data:
            self._location = data['location']
            self._folder_id = None # invalidate the folder
        if 'credentials' in data:
            self._credentials = Credentials.new_from_json(json.dumps(data['credentials']))
        if 'authorization_key' in data:
            self._authorization_key = data['authorization_key']
        if 'folder_id' in data:
            self._folder_id = data['folder_id']

    def _get_folder_id(self):
        if not self._folder_id:
            self.debug('finding folder id for location "%s"' % self._location)
            self._folder_id = self._get_folder_id_by_path(self._location)
            save()

        return self._folder_id

    def _get_folder_id_by_path(self, path):
        path = [p.strip() for p in path.split('/') if p.strip()]

        parent_id = 'root'
        for name in path:
            parent_id = self._get_folder_id_by_name(parent_id, name)

        return parent_id

    def _get_folder_id_by_name(self, parent_id, child_name):
        query = self.CHILDREN_QUERY % {'parent_id': parent_id, 'child_name': child_name}
        query = urllib.quote(query)
        url = self.CHILDREN_URL % {'parent_id': parent_id, 'query': query}
        response = self._request(url)
        try:
            response = json.loads(response)

        except Exception:
            self.error("response doesn't seem to be a valid json")
            raise

        items = response.get('items')
        if not items:
            msg = 'folder with name "%s" could not be found' % child_name
            self.error(msg)
            raise Exception(msg)
        
        return items[0]['id']

    def _request(self, url, body=None, headers=None):
        if not self._authorization_key:
            msg = 'missing authorization key'
            self.error(msg)
            raise Exception(msg)

        if not self._credentials:
            self.debug('requesting access token')
            flow = self._get_oauth2_flow()
            try:
                self._credentials = flow.step2_exchange(self._authorization_key)
                save()
            
            except Exception as e:
                self.error('failed to obtain access token: %s' % e)
                raise

        headers = headers or {}
        headers['Authorization'] = 'Bearer %s' % self._credentials.access_token

        self.debug('requesting %s' % url)
        request = urllib2.Request(url, data=body, headers=headers)
        try:
            response = urllib2.urlopen(request)
        
        except urllib2.HTTPError as e:
            if e.code == 403: # unauthorized, access token may have expired
                try:
                    self.debug('access token might have expired, refreshing it')
                    self._credentials.refresh(httplib2.Http())
                    save()

                except Exception as e:
                    self.error('refreshing access token failed')
                    raise
                
            else:
                self.error('request failed: %s' % e)
                raise

        except Exception as e:
            self.error('request failed: %s' % e)
            raise

        return response.read()

    def _get_oauth2_flow(self):
        return OAuth2WebServerFlow(client_id=self.CLIENT_ID, client_secret=self.CLIENT_NOT_SO_SECRET,
                scope=self.SCOPE, redirect_uri='urn:ietf:wg:oauth:2.0:oob')


def get(camera_id, name, create=True):
    camera_id = str(camera_id)
    service = _services.get(camera_id, {}).get(name)
    if not service and create:
        classes = UploadService.get_service_classes()
        cls = classes.get(name)
        if cls:
            logging.debug('creating upload service %s for camera with id %s' % (name, camera_id))
            service = cls()
            _services.setdefault(camera_id, {})[name] = service

    return service


def load():
    file_path = os.path.join(settings.CONF_PATH, _STATE_FILE_NAME)
    
    if os.path.exists(file_path):
        logging.debug('loading upload services state from "%s"...' % file_path)
    
        try:
            file = open(file_path, 'r')
        
        except Exception as e:
            logging.error('could not open upload services state file "%s": %s' % (file_path, e))
            
            return

        try:
            data = json.load(file)

        except Exception as e:
            return logging.error('could not read upload services state from file "%s": %s'(file_path, e))

        finally:
            file.close()

        for camera_id, d in data.iteritems():
            for name, state in d.iteritems():
                camera_services = _services.setdefault(camera_id, {})
                cls = UploadService.get_service_classes().get(name)
                if cls:
                    service = cls()
                    service.load(state)

                    camera_services[name] = service
    
                    logging.debug('loaded upload service "%s" for camera with id "%s"' % (name, camera_id))


def save():
    file_path = os.path.join(settings.CONF_PATH, _STATE_FILE_NAME)
    
    logging.debug('saving upload services state to "%s"...' % file_path)

    try:
        file = open(file_path, 'w')

    except Exception as e:
        logging.error('could not open upload services state file "%s": %s' % (file_path, e))
        
        return
    
    data = {}
    for camera_id, camera_services in _services.iteritems():
        for name, service in camera_services.iteritems():
            data.setdefault(camera_id, {})[name] = service.dump()

    try:
        json.dump(data, file, sort_keys=True, indent=4)

    except Exception as e:
        logging.error('could not save upload services state to file "%s": %s'(file_path, e))

    finally:
        file.close()


def upload_media_file(camera_id, service_name, filename):
    service = get(camera_id, service_name, create=False)
    if not service:
        return logging.error('service "%s" not initialized for camera with id %s' % (service_name, camera_id))

    try:
        service.upload_file(filename)

    except Exception as e:
        logging.error('failed to upload file "%s" with service %s: %s' % (filename, service, e))
