
import json
import logging

from tornado.httpclient import AsyncHTTPClient, HTTPClient, HTTPRequest


def _make_request(host, port, username, password, uri, method='GET', data=None, query=None):
    url = '%(scheme)s://%(host)s:%(port)s%(uri)s' % {
            'scheme': 'http',
            'host': host,
            'port': port,
            'uri': uri}
    
    if query:
        url += '?' + '='.join(query.items())
        
    request = HTTPRequest(url, method, body=data, auth_username=username, auth_password=password)
    
    return request


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


def current_snapshot(host, port, username, password, camera_id, callback):
    logging.debug('getting current snapshot for remote camera %(id)s on %(host)s:%(port)s' % {
            'id': camera_id,
            'host': host,
            'port': port})
    
    request = _make_request(host, port, username, password, '/snapshot/%(id)s/current/' % {'id': camera_id})
    
    def on_response(response):
        if response.error:
            logging.error('failed to get current snapshot for remote camera %(id)s on %(host)s:%(port)s: %(msg)s' % {
                    'id': camera_id,
                    'host': host,
                    'port': port,
                    'msg': unicode(response.error)})
            
            return callback(None)
        
        callback(response.body)
    
    http_client = AsyncHTTPClient()
    http_client.fetch(request, on_response)
