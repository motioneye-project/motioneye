
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

import functools
import json
import logging
import re

from tornado.httpclient import AsyncHTTPClient, HTTPRequest

import settings
import utils

_DOUBLE_SLASH_REGEX = re.compile('//+')


def _make_request(scheme, host, port, username, password, path, method='GET', data=None, query=None, timeout=None):
    path = _DOUBLE_SLASH_REGEX.sub('/', path)
    url = '%(scheme)s://%(host)s%(port)s%(path)s' % {
            'scheme': scheme,
            'host': host,
            'port': ':' + str(port) if port else '',
            'path': path or ''}
    
    query = dict(query or {})
    query['_username'] = username or ''
    query['_admin'] = 'true' # always use the admin account
    
    if url.count('?'):
        url += '&'
        
    else:
        url += '?'
    
    url += '&'.join([(n + '=' + v) for (n, v) in query.iteritems()])
    url += '&_signature=' + utils.compute_signature(method, url, data, password)

    if timeout is None:
        timeout = settings.REMOTE_REQUEST_TIMEOUT
        
    return HTTPRequest(url, method, body=data, connect_timeout=timeout, request_timeout=timeout)


def _callback_wrapper(callback):
    @functools.wraps(callback)
    def wrapper(response):
        try:
            decoded = json.loads(response.body)
            if decoded['error'] == 'unauthorized':
                response.error = 'Authentication Error'
                
            elif decoded['error']:
                response.error = decoded['error']

        except:
            pass
        
        return callback(response)
    
    return wrapper


def pretty_camera_url(local_config, camera=True):
    scheme = local_config.get('@scheme', local_config.get('scheme')) or 'http'
    host = local_config.get('@host', local_config.get('host'))
    port = local_config.get('@port', local_config.get('port'))
    path = local_config.get('@path', local_config.get('path')) or ''

    url = scheme + '://' + host
    if port and str(port) not in ['80', '443']:
        url += ':' + str(port)
    
    if path:
        url += path
        
    if url.endswith('/'):
        url = url[:-1]

    if camera:
        if camera is True:
            url += '/config/' + str(local_config.get('@remote_camera_id', local_config.get('remote_camera_id')))
        
        else:
            url += '/config/' + str(camera)

    return url


def _remote_params(local_config):
    return (
            local_config.get('@scheme', local_config.get('scheme')) or 'http',
            local_config.get('@host', local_config.get('host')),
            local_config.get('@port', local_config.get('port')),
            local_config.get('@username', local_config.get('username')),
            local_config.get('@password', local_config.get('password')),
            local_config.get('@path', local_config.get('path')) or '',
            local_config.get('@remote_camera_id', local_config.get('remote_camera_id')))


def list(local_config, callback):
    scheme, host, port, username, password, path, _ = _remote_params(local_config)
    
    logging.debug('listing remote cameras on %(url)s' % {
            'url': pretty_camera_url(local_config, camera=False)})
    
    request = _make_request(scheme, host, port, username, password, path + '/config/list/')
    
    def on_response(response):
        def make_camera_response(c):
            return {
                'id': c['id'],
                'name': c['name']
            }
        
        if response.error:
            logging.error('failed to list remote cameras on %(url)s: %(msg)s' % {
                    'url': pretty_camera_url(local_config, camera=False),
                    'msg': utils.pretty_http_error(response)})
            
            return callback(error=utils.pretty_http_error(response))
        
        try:
            response = json.loads(response.body)
            
        except Exception as e:
            logging.error('failed to decode json answer from %(url)s: %(msg)s' % {
                    'url': pretty_camera_url(local_config, camera=False),
                    'msg': unicode(e)})
            
            return callback(error=unicode(e))
        
        cameras = response['cameras']
        
        # filter out simple mjpeg cameras
        cameras = [make_camera_response(c) for c in cameras
                if c['proto'] != 'mjpeg' and c.get('enabled')]
        
        callback(cameras)
    
    http_client = AsyncHTTPClient()
    http_client.fetch(request, _callback_wrapper(on_response))
    

def get_config(local_config, callback):
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)
     
    logging.debug('getting config for remote camera %(id)s on %(url)s' % {
            'id': camera_id,
            'url': pretty_camera_url(local_config)})
    
    request = _make_request(scheme, host, port, username, password, path + '/config/%(id)s/get/' % {'id': camera_id})
    
    def on_response(response):
        if response.error:
            logging.error('failed to get config for remote camera %(id)s on %(url)s: %(msg)s' % {
                    'id': camera_id,
                    'url': pretty_camera_url(local_config),
                    'msg': utils.pretty_http_error(response)})
            
            return callback(error=utils.pretty_http_error(response))
    
        try:
            response = json.loads(response.body)
        
        except Exception as e:
            logging.error('failed to decode json answer from %(url)s: %(msg)s' % {
                    'url': pretty_camera_url(local_config),
                    'msg': unicode(e)})
            
            return callback(error=unicode(e))
        
        response['host'] = host
        response['port'] = port
            
        callback(response)
    
    http_client = AsyncHTTPClient()
    http_client.fetch(request, _callback_wrapper(on_response))
    

def set_config(local_config, ui_config, callback):
    scheme = local_config.get('@scheme', local_config.get('scheme'))
    host = local_config.get('@host', local_config.get('host')) 
    port = local_config.get('@port', local_config.get('port'))
    username = local_config.get('@username', local_config.get('username'))
    password = local_config.get('@password', local_config.get('password'))
    path = local_config.get('@path', local_config.get('path')) or ''
    camera_id = local_config.get('@remote_camera_id', local_config.get('remote_camera_id'))

    logging.debug('setting config for remote camera %(id)s on %(url)s' % {
            'id': camera_id,
            'url': pretty_camera_url(local_config)})
    
    ui_config = json.dumps(ui_config)
    
    request = _make_request(scheme, host, port, username, password, path + '/config/%(id)s/set/' % {'id': camera_id}, method='POST', data=ui_config)
    
    def on_response(response):
        if response.error:
            logging.error('failed to set config for remote camera %(id)s on %(url)s: %(msg)s' % {
                    'id': camera_id,
                    'url': pretty_camera_url(local_config),
                    'msg': utils.pretty_http_error(response)})
            
            return callback(error=utils.pretty_http_error(response))
    
        callback()

    http_client = AsyncHTTPClient()
    http_client.fetch(request, _callback_wrapper(on_response))


def set_preview(local_config, controls, callback):
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)
    
    logging.debug('setting preview for remote camera %(id)s on %(url)s' % {
            'id': camera_id,
            'url': pretty_camera_url(local_config)})
    
    data = json.dumps(controls)
    
    request = _make_request(scheme, host, port, username, password, path + '/config/%(id)s/set_preview/' % {'id': camera_id}, method='POST', data=data)

    def on_response(response):
        if response.error:
            logging.error('failed to set preview for remote camera %(id)s on %(url)s: %(msg)s' % {
                    'id': camera_id,
                    'url': pretty_camera_url(local_config),
                    'msg': utils.pretty_http_error(response)})
        
            return callback(error=utils.pretty_http_error(response))
        
        callback()

    http_client = AsyncHTTPClient()
    http_client.fetch(request, _callback_wrapper(on_response))


def get_current_picture(local_config, width, height, callback):
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)
    
    logging.debug('getting current picture for remote camera %(id)s on %(url)s' % {
            'id': camera_id,
            'url': pretty_camera_url(local_config)})
    
    query = {}
    
    if width:
        query['width'] = str(width)
        
    if height:
        query['height'] = str(height)
    
    request = _make_request(scheme, host, port, username, password, path + '/picture/%(id)s/current/' % {'id': camera_id}, query=query)
    
    def on_response(response):
        motion_detected = False
        
        cookies = response.headers.get('Set-Cookie')
        if cookies:
            cookies = cookies.split(';')
            cookies = [[i.strip() for i in c.split('=')] for c in cookies]
            cookies = dict([c for c in cookies if len(c) == 2])
            motion_detected = cookies.get('motion_detected_' + str(camera_id)) == 'true'
        
        if response.error:
            logging.error('failed to get current picture for remote camera %(id)s on %(url)s: %(msg)s' % {
                    'id': camera_id,
                    'url': pretty_camera_url(local_config),
                    'msg': utils.pretty_http_error(response)})
            
            return callback(error=utils.pretty_http_error(response))

        callback(motion_detected, response.body)
    
    http_client = AsyncHTTPClient()
    http_client.fetch(request, _callback_wrapper(on_response))


def list_media(local_config, media_type, prefix, callback):
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)
    
    logging.debug('getting media list for remote camera %(id)s on %(url)s' % {
            'id': camera_id,
            'url': pretty_camera_url(local_config)})
    
    query = {}
    if prefix is not None:
        query['prefix'] = prefix
    
    # timeout here is 10 times larger than usual - we expect a big delay when fetching the media list
    request = _make_request(scheme, host, port, username, password, path + '/%(media_type)s/%(id)s/list/' % {
            'id': camera_id, 'media_type': media_type}, query=query, timeout=10 * settings.REMOTE_REQUEST_TIMEOUT)
    
    def on_response(response):
        if response.error:
            logging.error('failed to get media list for remote camera %(id)s on %(url)s: %(msg)s' % {
                    'id': camera_id,
                    'url': pretty_camera_url(local_config),
                    'msg': utils.pretty_http_error(response)})
            
            return callback(error=utils.pretty_http_error(response))
        
        try:
            response = json.loads(response.body)
            
        except Exception as e:
            logging.error('failed to decode json answer from %(url)s: %(msg)s' % {
                    'url': pretty_camera_url(local_config),
                    'msg': unicode(e)})
            
            return callback(error=unicode(e))
        
        return callback(response)
    
    http_client = AsyncHTTPClient()
    http_client.fetch(request, _callback_wrapper(on_response))


def get_media_content(local_config, filename, media_type, callback):
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)
    
    logging.debug('downloading file %(filename)s of remote camera %(id)s on %(url)s' % {
            'filename': filename,
            'id': camera_id,
            'url': pretty_camera_url(local_config)})
    
    path += '/%(media_type)s/%(id)s/download/%(filename)s' % {
            'media_type': media_type,
            'id': camera_id,
            'filename': filename}
    
    # timeout here is 10 times larger than usual - we expect a big delay when fetching the media list
    request = _make_request(scheme, host, port, username, password, path, timeout=10 * settings.REMOTE_REQUEST_TIMEOUT)
    
    def on_response(response):
        if response.error:
            logging.error('failed to download file %(filename)s of remote camera %(id)s on %(url)s: %(msg)s' % {
                    'filename': filename,
                    'id': camera_id,
                    'url': pretty_camera_url(local_config),
                    'msg': utils.pretty_http_error(response)})
            
            return callback(error=utils.pretty_http_error(response))
        
        return callback(response.body)

    http_client = AsyncHTTPClient()
    http_client.fetch(request, _callback_wrapper(on_response))


def make_zipped_content(local_config, media_type, group, callback):
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)
    
    logging.debug('preparing zip file for group %(group)s of remote camera %(id)s on %(url)s' % {
            'group': group,
            'id': camera_id,
            'url': pretty_camera_url(local_config)})

    prepare_path = path + '/%(media_type)s/%(id)s/zipped/%(group)s/' % {
            'media_type': media_type,
            'id': camera_id,
            'group': group}
 
    # timeout here is 100 times larger than usual - we expect a big delay
    request = _make_request(scheme, host, port, username, password, prepare_path, timeout=100 * settings.REMOTE_REQUEST_TIMEOUT)

    def on_response(response):
        if response.error:
            logging.error('failed to prepare zip file for group %(group)s of remote camera %(id)s on %(url)s: %(msg)s' % {
                    'group': group,
                    'id': camera_id,
                    'url': pretty_camera_url(local_config),
                    'msg': utils.pretty_http_error(response)})

            return callback(error=utils.pretty_http_error(response))
        
        try:
            key = json.loads(response.body)['key']

        except Exception as e:
            logging.error('failed to decode json answer from %(url)s: %(msg)s' % {
                    'url': pretty_camera_url(local_config),
                    'msg': unicode(e)})

            return callback(error=unicode(e))

        callback({'key': key})

    http_client = AsyncHTTPClient()
    http_client.fetch(request, _callback_wrapper(on_response))


def get_zipped_content(local_config, media_type, key, group, callback):
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)
    
    logging.debug('downloading zip file for remote camera %(id)s on %(url)s' % {
            'id': camera_id,
            'url': pretty_camera_url(local_config)})
    
    request = _make_request(scheme, host, port, username, password, path + '/%(media_type)s/%(id)s/zipped/%(group)s/?key=%(key)s' % {
            'media_type': media_type,
            'group': group,
            'id': camera_id,
            'key': key},
            timeout=10 * settings.REMOTE_REQUEST_TIMEOUT)

    def on_response(response):
        if response.error:
            logging.error('failed to download zip file for remote camera %(id)s on %(url)s: %(msg)s' % {
                    'id': camera_id,
                    'url': pretty_camera_url(local_config),
                    'msg': utils.pretty_http_error(response)})

            return callback(error=utils.pretty_http_error(response))

        callback({
            'data': response.body,
            'content_type': response.headers.get('Content-Type'),
            'content_disposition': response.headers.get('Content-Disposition')
        })

    http_client = AsyncHTTPClient()
    http_client.fetch(request, _callback_wrapper(on_response))


def make_timelapse_movie(local_config, framerate, interval, group, callback):
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)

    logging.debug('making timelapse movie for group %(group)s of remote camera %(id)s with rate %(framerate)s/%(int)s on %(url)s' % {
            'group': group,
            'id': camera_id,
            'framerate': framerate,
            'int': interval,
            'url': pretty_camera_url(local_config)})

    path += '/picture/%(id)s/timelapse/%(group)s/?interval=%(int)s&framerate=%(framerate)s' % {
            'id': camera_id,
            'int': interval,
            'framerate': framerate,
            'group': group}
    
    request = _make_request(scheme, host, port, username, password, path, timeout=100 * settings.REMOTE_REQUEST_TIMEOUT)

    def on_response(response):
        if response.error:
            logging.error('failed to make timelapse movie for group %(group)s of remote camera %(id)s with rate %(framerate)s/%(int)s on %(url)s: %(msg)s' % {
                    'group': group,
                    'id': camera_id,
                    'url': pretty_camera_url(local_config),
                    'int': interval,
                    'framerate': framerate,
                    'msg': utils.pretty_http_error(response)})

            return callback(error=utils.pretty_http_error(response))
        
        try:
            response = json.loads(response.body)

        except Exception as e:
            logging.error('failed to decode json answer from %(url)s: %(msg)s' % {
                    'url': pretty_camera_url(local_config),
                    'msg': unicode(e)})

            return callback(error=unicode(e))
        
        callback(response)

    http_client = AsyncHTTPClient()
    http_client.fetch(request, _callback_wrapper(on_response))


def check_timelapse_movie(local_config, group, callback):
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)
    
    logging.debug('checking timelapse movie status for remote camera %(id)s on %(url)s' % {
            'id': camera_id,
            'url': pretty_camera_url(local_config)})
    
    request = _make_request(scheme, host, port, username, password, path + '/picture/%(id)s/timelapse/%(group)s/?check=true' % {
            'id': camera_id,
            'group': group})
    
    def on_response(response):
        if response.error:
            logging.error('failed to check timelapse movie status for remote camera %(id)s on %(url)s: %(msg)s' % {
                    'id': camera_id,
                    'url': pretty_camera_url(local_config),
                    'msg': utils.pretty_http_error(response)})

            return callback(error=utils.pretty_http_error(response))
        
        try:
            response = json.loads(response.body)

        except Exception as e:
            logging.error('failed to decode json answer from %(url)s: %(msg)s' % {
                    'url': pretty_camera_url(local_config),
                    'msg': unicode(e)})

            return callback(error=unicode(e))
        
        callback(response)

    http_client = AsyncHTTPClient()
    http_client.fetch(request, _callback_wrapper(on_response))


def get_timelapse_movie(local_config, key, group, callback):
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)
    
    logging.debug('downloading timelapse movie for remote camera %(id)s on %(url)s' % {
            'id': camera_id,
            'url': pretty_camera_url(local_config)})
    
    request = _make_request(scheme, host, port, username, password, path + '/picture/%(id)s/timelapse/%(group)s/?key=%(key)s' % {
            'id': camera_id,
            'group': group,
            'key': key},
            timeout=10 * settings.REMOTE_REQUEST_TIMEOUT)

    def on_response(response):
        if response.error:
            logging.error('failed to download timelapse movie for remote camera %(id)s on %(url)s: %(msg)s' % {
                    'id': camera_id,
                    'url': pretty_camera_url(local_config),
                    'msg': utils.pretty_http_error(response)})

            return callback(error=utils.pretty_http_error(response))

        callback({
            'data': response.body,
            'content_type': response.headers.get('Content-Type'),
            'content_disposition': response.headers.get('Content-Disposition')
        })

    http_client = AsyncHTTPClient()
    http_client.fetch(request, _callback_wrapper(on_response))


def get_media_preview(local_config, filename, media_type, width, height, callback):
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)
    
    logging.debug('getting file preview for %(filename)s of remote camera %(id)s on %(url)s' % {
            'filename': filename,
            'id': camera_id,
            'url': pretty_camera_url(local_config)})
    
    path += '/%(media_type)s/%(id)s/preview/%(filename)s' % {
            'media_type': media_type,
            'id': camera_id,
            'filename': filename}
    
    query = {}
    
    if width:
        query['width'] = str(width)
        
    if height:
        query['height'] = str(height)
    
    request = _make_request(scheme, host, port, username, password, path, query=query)
    
    def on_response(response):
        if response.error:
            logging.error('failed to get file preview for %(filename)s of remote camera %(id)s on %(url)s: %(msg)s' % {
                    'filename': filename,
                    'id': camera_id,
                    'url': pretty_camera_url(local_config),
                    'msg': utils.pretty_http_error(response)})
            
            return callback(error=utils.pretty_http_error(response))
        
        callback(response.body)

    http_client = AsyncHTTPClient()
    http_client.fetch(request, _callback_wrapper(on_response))


def del_media_content(local_config, filename, media_type, callback):
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)
    
    logging.debug('deleting file %(filename)s of remote camera %(id)s on %(url)s' % {
            'filename': filename,
            'id': camera_id,
            'url': pretty_camera_url(local_config)})
    
    path += '/%(media_type)s/%(id)s/delete/%(filename)s' % {
            'media_type': media_type,
            'id': camera_id,
            'filename': filename}

    request = _make_request(scheme, host, port, username, password, path, method='POST', data='{}', timeout=settings.REMOTE_REQUEST_TIMEOUT)

    def on_response(response):
        if response.error:
            logging.error('failed to delete file %(filename)s of remote camera %(id)s on %(url)s: %(msg)s' % {
                    'filename': filename,
                    'id': camera_id,
                    'url': pretty_camera_url(local_config),
                    'msg': utils.pretty_http_error(response)})
            
            return callback(error=utils.pretty_http_error(response))
        
        callback()

    http_client = AsyncHTTPClient()
    http_client.fetch(request, _callback_wrapper(on_response))


def del_media_group(local_config, group, media_type, callback):
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)
    
    logging.debug('deleting group %(group)s of remote camera %(id)s on %(url)s' % {
            'group': group,
            'id': camera_id,
            'url': pretty_camera_url(local_config)})
    
    path += '/%(media_type)s/%(id)s/delete_all/%(group)s/' % {
            'media_type': media_type,
            'id': camera_id,
            'group': group}

    request = _make_request(scheme, host, port, username, password, path, method='POST', data='{}', timeout=settings.REMOTE_REQUEST_TIMEOUT)

    def on_response(response):
        if response.error:
            logging.error('failed to delete group %(group)s of remote camera %(id)s on %(url)s: %(msg)s' % {
                    'group': group,
                    'id': camera_id,
                    'url': pretty_camera_url(local_config),
                    'msg': utils.pretty_http_error(response)})
            
            return callback(error=utils.pretty_http_error(response))
        
        callback()

    http_client = AsyncHTTPClient()
    http_client.fetch(request, _callback_wrapper(on_response))
