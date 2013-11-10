
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

from tornado.httpclient import AsyncHTTPClient, HTTPClient, HTTPRequest

import settings

_snapshot_cache = {}


def _make_request(host, port, username, password, uri, method='GET', data=None, query=None):
    url = '%(scheme)s://%(host)s:%(port)s%(uri)s' % {
            'scheme': 'http',
            'host': host,
            'port': port,
            'uri': uri}
    
    if query:
        url += '?' + '='.join(query.items())
        
    request = HTTPRequest(url, method, body=data, auth_username=username, auth_password=password,
            request_timeout=settings.REMOTE_REQUEST_TIMEOUT)
    
    return request


def make_remote_camera_url(host, port, camera_id, proto=''):
    if proto:
        proto += '://'
        
    return '%(proto)s%(host)s:%(port)s/config/%(camera_id)s' % {
        'host': host,
        'port': port,
        'camera_id': camera_id,
        'proto': proto
    }


def list_cameras(host, port, username, password, callback):
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
    

def get_config(host, port, username, password, camera_id, callback):
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
            
        callback(response)
    
    http_client = AsyncHTTPClient()
    http_client.fetch(request, on_response)
    

def set_config(host, port, username, password, camera_id, data):
    logging.debug('setting config for remote camera %(id)s on %(host)s:%(port)s' % {
            'id': camera_id,
            'host': host,
            'port': port})
    
    data = json.dumps(data)
    
    request = _make_request(host, port, username, password, '/config/%(id)s/set/' % {'id': camera_id}, method='POST', data=data)
    
    try:
        http_client = HTTPClient()
        response = http_client.fetch(request)
        if response.error:
            raise Exception(unicode(response.error)) 
    
    except Exception as e:
        logging.error('failed to set config for remote camera %(id)s on %(host)s:%(port)s: %(msg)s' % {
                'id': camera_id,
                'host': host,
                'port': port,
                'msg': unicode(e)})
        
        raise


def set_preview(host, port, username, password, camera_id, controls, callback):
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


def current_picture(host, port, username, password, camera_id, callback):
    global _snapshot_cache
    
    logging.debug('getting current picture for remote camera %(id)s on %(host)s:%(port)s' % {
            'id': camera_id,
            'host': host,
            'port': port})
    
    request = _make_request(host, port, username, password, '/picture/%(id)s/current/' % {'id': camera_id})
    
    cached = _snapshot_cache.setdefault(request.url, {'pending': 0, 'jpg': None})
    if cached['pending'] > 0: # a pending request for this snapshot exists
        return callback(cached['jpg'])
    
    def on_response(response):
        cached['pending'] -= 1
        cached['jpg'] = response.body
        
        if response.error:
            logging.error('failed to get current picture for remote camera %(id)s on %(host)s:%(port)s: %(msg)s' % {
                    'id': camera_id,
                    'host': host,
                    'port': port,
                    'msg': unicode(response.error)})
            
            return callback(None)
        
        callback(response.body)
    
    cached['pending'] += 1
    
    http_client = AsyncHTTPClient()
    http_client.fetch(request, on_response)


def list_pictures(host, port, username, password, camera_id, callback):
    logging.debug('getting picture list for remote camera %(id)s on %(host)s:%(port)s' % {
            'id': camera_id,
            'host': host,
            'port': port})
    
    request = _make_request(host, port, username, password, '/picture/%(id)s/list/' % {'id': camera_id})
    
    def on_response(response):
        if response.error:
            logging.error('failed to get picture list for remote camera %(id)s on %(host)s:%(port)s: %(msg)s' % {
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


def preview_picture(host, port, username, password, camera_id, filename, width, height, callback):
    logging.debug('getting preview for file %(filename)s of remote camera %(id)s on %(host)s:%(port)s' % {
            'filename': filename,
            'id': camera_id,
            'host': host,
            'port': port})
    
    uri = '/picture/%(id)s/preview/%(filename)s/?' % {
            'id': camera_id,
            'filename': filename}
    
    if width:
        uri += 'width=' + str(width)
    if height:
        uri += 'height=' + str(height)
    
    request = _make_request(host, port, username, password, uri)
    
    def on_response(response):
        if response.error:
            logging.error('failed to get preview for file %(filename)s of remote camera %(id)s on %(host)s:%(port)s: %(msg)s' % {
                    'filename': filename,
                    'id': camera_id,
                    'host': host,
                    'port': port,
                    'msg': unicode(response.error)})
            
            return callback(None)
        
        return callback(response.body)

    http_client = AsyncHTTPClient()
    http_client.fetch(request, on_response)
