
import json
import logging

from tornado.web import RequestHandler, HTTPError

import template


class BaseHandler(RequestHandler):
    def render(self, template_name, content_type='text/html', **context):
        self.set_header('Content-Type', content_type)
        
        content = template.render(template_name, **context)
        self.finish(content)
    
    def finish_json(self, data={}):
        self.set_header('Content-Type', 'application/json')
        self.finish(json.dumps(data))


class MainHandler(BaseHandler):
    def get(self):
        self.render('main.html')


class ConfigHandler(BaseHandler):
    def get(self, camera_id=None, op=None):
        if op == 'get':
            self.get_config(camera_id)
        
        else:
            raise HTTPError(400, 'unknown operation')
    
    def post(self, camera_id=None, op=None):
        if op == 'set':
            self.set_config(camera_id)
        
        elif op == 'add':
            self.add_camera()
        
        elif op == 'rem':
            self.rem_camera(camera_id)
        
        else:
            raise HTTPError(400, 'unknown operation')
    
    def get_config(self, camera_id):
        if camera_id:
            logging.debug('getting config for camera %(id)s' % {'camera': camera_id})
            
        else:
            logging.debug('getting general config')
    
    def set_config(self, camera_id):
        if camera_id:
            logging.debug('setting config for camera %(id)s' % {'camera': camera_id})
            
        else:
            logging.debug('setting general config')
    
    def add_camera(self):
        logging.debug('adding new camera')
    
    def rem_camera(self, camera_id):
        logging.debug('removing camera %(id)s' % {'camera': camera_id})


class SnapshotHandler(BaseHandler):
    def get(self, camera_id, op, filename=None):
        if op == 'current':
            self.current()
            
        elif op == 'list':
            self.list(camera_id)
            
        elif op == 'download':
            self.download(filename)
        
        else:
            raise HTTPError(400, 'unknown operation')
    
    def current(self):
        pass
    
    def list(self, camera_id):
        logging.debug('listing snapshots for camera %(id)s' % {'camera': camera_id})
    
    def download(self, camera_id, filename):
        logging.debug('downloading snapshot %(filename)s of camera %(id)s' % {
                'filename': filename, 'camera': camera_id})


class MovieHandler(BaseHandler):
    def get(self, camera_id, op, filename=None):
        if op == 'list':
            self.list(camera_id)
            
        elif op == 'download':
            self.download(camera_id, filename)
        
        else:
            raise HTTPError(400, 'unknown operation')
    
    def list(self, camera_id):
        logging.debug('listing movies for camera %(id)s' % {'camera': camera_id})
    
    def download(self, camera_id, filename):
        logging.debug('downloading movie %(filename)s of camera %(id)s' % {
                'filename': filename, 'camera': camera_id})
