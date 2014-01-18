
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

import json
import logging

from tornado.httpclient import AsyncHTTPClient, HTTPRequest

import settings


def _make_request(host, port, username, password, uri, method='GET', data=None, query=None, timeout=None):
    url = '%(scheme)s://%(host)s:%(port)s%(uri)s' % {
            'scheme': 'http',
            'host': host,
            'port': port,
            'uri': uri}
    
    if query:
        url += '?' + '&'.join([(n + '=' + v) for (n, v) in query.iteritems()])
    
    if timeout is None:
        timeout = settings.REMOTE_REQUEST_TIMEOUT
        
    request = HTTPRequest(url, method, body=data, auth_username=username, auth_password=password,
            request_timeout=timeout)
    
    return request


def make_camera_uri(camera_id):
    return '/config/%(camera_id)s' % {'camera_id': camera_id}


def list_cameras(local_config, callback):
    host = local_config.get('@host', local_config.get('host')) 
    port = local_config.get('@port', local_config.get('port'))
    username = local_config.get('@username', local_config.get('username'))
    password = local_config.get('@password', local_config.get('password'))
    
    logging.debug('listing remote cameras on %(host)s:%(port)s' % {
            'host': host,
            'port': port})
    
    request = _make_request(host, port, username, password, '/config/list/')
    
    def on_response(response):
        if response.error:
            logging.error('failed to list remote cameras on %(host)s:%(port)s: %(msg)s' % {
                    'host': host,
                    'port': port,
                    'msg': unicode(response.error)})
            
            return callback(None)
        
        try:
            response = json.loads(response.body)
            
        except Exception as e:
            logging.error('failed to decode json answer from %(host)s:%(port)s: %(msg)s' % {
                    'host': host,
                    'port': port,
                    'msg': unicode(e)})
            
            return callback(None)
        
        return callback(response['cameras'])
    
    http_client = AsyncHTTPClient()
    http_client.fetch(request, on_response)
    

def get_config(local_config, callback):
    host = local_config.get('@host', local_config.get('host')) 
    port = local_config.get('@port', local_config.get('port'))
    username = local_config.get('@username', local_config.get('username'))
    password = local_config.get('@password', local_config.get('password'))
    camera_id = local_config.get('@remote_camera_id', local_config.get('remote_camera_id'))
     
    logging.debug('getting config for remote camera %(id)s on %(host)s:%(port)s' % {
            'id': camera_id,
            'host': host,
            'port': port})
    
    request = _make_request(host, port, username, password, '/config/%(id)s/get/' % {'id': camera_id})
    
    def on_response(response):
        if response.error:
            logging.error('failed to get config for remote camera %(id)s on %(host)s:%(port)s: %(msg)s' % {
                    'id': camera_id,
                    'host': host,
                    'port': port,
                    'msg': unicode(response.error)})
            
            return callback(None)
    
        try:
            response = json.loads(response.body)
        
        except Exception as e:
            logging.error('failed to decode json answer from %(host)s:%(port)s: %(msg)s' % {
                    'host': host,
                    'port': port,
                    'msg': unicode(e)})
            
            return callback(None)
        
        response['host'] = host
        response['port'] = port
        response['device_uri'] = make_camera_uri(camera_id)
            
        callback(response)
    
    http_client = AsyncHTTPClient()
    http_client.fetch(request, on_response)
    

def set_config(local_config, ui_config, callback):
    host = local_config.get('@host', local_config.get('host')) 
    port = local_config.get('@port', local_config.get('port'))
    username = local_config.get('@username', local_config.get('username'))
    password = local_config.get('@password', local_config.get('password'))
    camera_id = local_config.get('@remote_camera_id', local_config.get('remote_camera_id'))
    
    logging.debug('setting config for remote camera %(id)s on %(host)s:%(port)s' % {
            'id': camera_id,
            'host': host,
            'port': port})
    
    ui_config = json.dumps(ui_config)
    
    request = _make_request(host, port, username, password, '/config/%(id)s/set/' % {'id': camera_id}, method='POST', data=ui_config)
    
    def on_response(response):
        if response.error:
            logging.error('failed to set config for remote camera %(id)s on %(host)s:%(port)s: %(msg)s' % {
                    'id': camera_id,
                    'host': host,
                    'port': port,
                    'msg': unicode(response.error)})
            
            return callback(response.error)
    
        callback(None)

    http_client = AsyncHTTPClient()
    http_client.fetch(request, on_response)


def set_preview(local_config, controls, callback):
    host = local_config.get('@host', local_config.get('host')) 
    port = local_config.get('@port', local_config.get('port'))
    username = local_config.get('@username', local_config.get('username'))
    password = local_config.get('@password', local_config.get('password'))
    camera_id = local_config.get('@remote_camera_id', local_config.get('remote_camera_id'))
    
    logging.debug('setting preview for remote camera %(id)s on %(host)s:%(port)s' % {
            'id': camera_id,
            'host': host,
            'port': port})
    
    data = json.dumps(controls)
    
    request = _make_request(host, port, username, password, '/config/%(id)s/set_preview/' % {'id': camera_id}, method='POST', data=data)

    def on_response(response):
        if response.error:
            logging.error('failed to set preview for remote camera %(id)s on %(host)s:%(port)s: %(msg)s' % {
                    'id': camera_id,
                    'host': host,
                    'port': port,
                    'msg': unicode(response.error)})
        
            return callback(None)
        
        callback('')

    http_client = AsyncHTTPClient()
    http_client.fetch(request, on_response)


def get_current_picture(local_config, callback, width, height):
    host = local_config.get('@host', local_config.get('host')) 
    port = local_config.get('@port', local_config.get('port'))
    username = local_config.get('@username', local_config.get('username'))
    password = local_config.get('@password', local_config.get('password'))
    camera_id = local_config.get('@remote_camera_id', local_config.get('remote_camera_id'))
    
    logging.debug('getting current picture for remote camera %(id)s on %(host)s:%(port)s' % {
            'id': camera_id,
            'host': host,
            'port': port})
    
    query = {}
    
    if width:
        query['width'] = str(width)
        
    if height:
        query['height'] = str(height)
    
    request = _make_request(host, port, username, password, '/picture/%(id)s/current/' % {'id': camera_id}, query=query)
    
    def on_response(response):
        if response.error:
            logging.error('failed to get current picture for remote camera %(id)s on %(host)s:%(port)s: %(msg)s' % {
                    'id': camera_id,
                    'host': host,
                    'port': port,
                    'msg': unicode(response.error)})
            
            return callback(None)
        
        callback(response.body)
    
    http_client = AsyncHTTPClient()
    http_client.fetch(request, on_response)


def list_media(local_config, callback, media_type, prefix=None):
    host = local_config.get('@host', local_config.get('host')) 
    port = local_config.get('@port', local_config.get('port'))
    username = local_config.get('@username', local_config.get('username'))
    password = local_config.get('@password', local_config.get('password'))
    camera_id = local_config.get('@remote_camera_id', local_config.get('remote_camera_id'))
    
    logging.debug('getting media list for remote camera %(id)s on %(host)s:%(port)s' % {
            'id': camera_id,
            'host': host,
            'port': port})
    
    query = {}
    if prefix is not None:
        query['prefix'] = prefix
    
    # timeout here is 10 times larger than usual - we expect a big delay when fetching the media list
    request = _make_request(host, port, username, password, '/%(media_type)s/%(id)s/list/' % {
            'id': camera_id, 'media_type': media_type}, query=query, timeout=10 * settings.REMOTE_REQUEST_TIMEOUT)
    
    def on_response(response):
        if response.error:
            logging.error('failed to get media list for remote camera %(id)s on %(host)s:%(port)s: %(msg)s' % {
                    'id': camera_id,
                    'host': host,
                    'port': port,
                    'msg': unicode(response.error)})
            
            return callback(None)
        
        try:
            response = json.loads(response.body)
            
        except Exception as e:
            logging.error('failed to decode json answer from %(host)s:%(port)s: %(msg)s' % {
                    'host': host,
                    'port': port,
                    'msg': unicode(e)})
            
            return callback(None)
        
        return callback(response)
    
    http_client = AsyncHTTPClient()
    http_client.fetch(request, on_response)


def get_media_content(local_config, callback, filename, media_type):
    host = local_config.get('@host', local_config.get('host'))
    port = local_config.get('@port', local_config.get('port'))
    username = local_config.get('@username', local_config.get('username'))
    password = local_config.get('@password', local_config.get('password'))
    camera_id = local_config.get('@remote_camera_id', local_config.get('remote_camera_id'))
    
    logging.debug('downloading file %(filename)s of remote camera %(id)s on %(host)s:%(port)s' % {
            'filename': filename,
            'id': camera_id,
            'host': host,
            'port': port})
    
    uri = '/%(media_type)s/%(id)s/download/%(filename)s' % {
            'media_type': media_type,
            'id': camera_id,
            'filename': filename}
    
    # timeout here is 10 times larger than usual - we expect a big delay when fetching the media list
    request = _make_request(host, port, username, password, uri, timeout=10 * settings.REMOTE_REQUEST_TIMEOUT)
    
    def on_response(response):
        if response.error:
            logging.error('failed to download file %(filename)s of remote camera %(id)s on %(host)s:%(port)s: %(msg)s' % {
                    'filename': filename,
                    'id': camera_id,
                    'host': host,
                    'port': port,
                    'msg': unicode(response.error)})
            
            return callback(None)
        
        return callback(response.body)

    http_client = AsyncHTTPClient()
    http_client.fetch(request, on_response)


def get_media_preview(local_config, callback, filename, media_type, width, height):
    host = local_config.get('@host', local_config.get('host'))
    port = local_config.get('@port', local_config.get('port'))
    username = local_config.get('@username', local_config.get('username'))
    password = local_config.get('@password', local_config.get('password'))
    camera_id = local_config.get('@remote_camera_id', local_config.get('remote_camera_id'))
    
    logging.debug('getting file preview for %(filename)s of remote camera %(id)s on %(host)s:%(port)s' % {
            'filename': filename,
            'id': camera_id,
            'host': host,
            'port': port})
    
    uri = '/%(media_type)s/%(id)s/preview/%(filename)s' % {
            'media_type': media_type,
            'id': camera_id,
            'filename': filename}
    
    query = {}
    
    if width:
        query['width'] = str(width)
        
    if height:
        query['height'] = str(height)
    
    request = _make_request(host, port, username, password, uri, query=query)
    
    def on_response(response):
        if response.error:
            logging.error('failed to get file preview for %(filename)s of remote camera %(id)s on %(host)s:%(port)s: %(msg)s' % {
                    'filename': filename,
                    'id': camera_id,
                    'host': host,
                    'port': port,
                    'msg': unicode(response.error)})
            
            return callback(None)
        
        return callback(response.body)

    http_client = AsyncHTTPClient()
    http_client.fetch(request, on_response)
