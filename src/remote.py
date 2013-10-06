
import json
import logging
import urllib2


def _compose_url(host, port, username, password, uri, query=None):
    url = '%(scheme)s://%(host)s:%(port)s%(uri)s' % {
            'scheme': 'http',
            'host': host,
            'port': port,
            'uri': uri}
    
    if query:
        url += '?' + '='.join(query.items())
    
    return url


def list_cameras(host, port, username, password):
    logging.debug('listing remote cameras on %(host)s:%(port)s' % {
            'host': host,
            'port': port})
    
    url = _compose_url(host, port, username, password, '/config/list/')
    request = urllib2.Request(url)
    
    try:
        response = urllib2.urlopen(request)
    
    except Exception as e:
        logging.error('failed to list remote cameras on %(host)s:%(port)s: %(msg)s' % {
                'host': host,
                'port': port,
                'msg': unicode(e)})
        
        raise
    
    try:
        response = json.load(response)
    
    except Exception as e:
        logging.error('failed to decode json answer from %(host)s:%(port)s: %(msg)s' % {
                'host': host,
                'port': port,
                'msg': unicode(e)})
        
        raise
    
    return response['cameras']


def get_config(host, port, username, password, camera_id):
    logging.debug('getting config for remote camera %(id)s on %(host)s:%(port)s' % {
            'id': camera_id,
            'host': host,
            'port': port})
    
    url = _compose_url(host, port, username, password, '/config/%(id)s/get/' % {'id': camera_id})
    request = urllib2.Request(url)
    
    try:
        response = urllib2.urlopen(request)
    
    except Exception as e:
        logging.error('failed to get config for remote camera %(id)s on %(host)s:%(port)s: %(msg)s' % {
                'id': camera_id,
                'host': host,
                'port': port,
                'msg': unicode(e)})
        
        raise
    
    try:
        response = json.load(response)
    
    except Exception as e:
        logging.error('failed to decode json answer from %(host)s:%(port)s: %(msg)s' % {
                'host': host,
                'port': port,
                'msg': unicode(e)})
        
        raise
    
    return response


def set_config(host, port, username, password, camera_id, data):
    logging.debug('setting config for remote camera %(id)s on %(host)s:%(port)s' % {
            'id': camera_id,
            'host': host,
            'port': port})
    
    data = json.dumps(data)
    
    url = _compose_url(host, port, username, password, '/config/%(id)s/set/' % {'id': camera_id})
    request = urllib2.Request(url, data=data)
    
    try:
        urllib2.urlopen(request)
    
    except Exception as e:
        logging.error('failed to set config for remote camera %(id)s on %(host)s:%(port)s: %(msg)s' % {
                'id': camera_id,
                'host': host,
                'port': port,
                'msg': unicode(e)})
        
        raise


def set_preview(host, port, username, password, camera_id, controls):
    logging.debug('setting preview for remote camera %(id)s on %(host)s:%(port)s' % {
            'id': camera_id,
            'host': host,
            'port': port})
    
    controls = json.dumps(controls)
    
    url = _compose_url(host, port, username, password, '/config/%(id)s/set_preview/' % {'id': camera_id})
    request = urllib2.Request(url, data=controls)
    
    try:
        urllib2.urlopen(request)
    
    except Exception as e:
        logging.error('failed to set preview for remote camera %(id)s on %(host)s:%(port)s: %(msg)s' % {
                'id': camera_id,
                'host': host,
                'port': port,
                'msg': unicode(e)})
        
        raise


def current_snapshot(host, port, username, password, camera_id):
    logging.debug('getting current snapshot for remote camera %(id)s on %(host)s:%(port)s' % {
            'id': camera_id,
            'host': host,
            'port': port})
    
    url = _compose_url(host, port, username, password, '/snapshot/%(id)s/current/' % {'id': camera_id})
    request = urllib2.Request(url)
    
    try:
        response = urllib2.urlopen(request)
    
    except Exception as e:
        logging.error('failed to get current snapshot for remote camera %(id)s on %(host)s:%(port)s: %(msg)s' % {
                'id': camera_id,
                'host': host,
                'port': port,
                'msg': unicode(e)})
        
        raise
    
    return response.read()
