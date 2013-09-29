
import logging
import re
import socket

from tornado import iostream

import config



class MjpgClient(iostream.IOStream):
    clients = {} # dictionary of clients indexed by camera id
    last_jpgs = {} # dictionary of jpg contents indexed by camera id
    
    def __init__(self, camera_id, port):
        self._camera_id = camera_id
        self._port = port
        
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        iostream.IOStream.__init__(self, s)
        
    def connect(self):
        iostream.IOStream.connect(self, ('localhost', self._port), self._on_connect)
        MjpgClient.clients[self._camera_id] = self
        
        logging.debug('mjpg client connecting on port %(port)s...' % {'port': self._port})
    
    def close(self):
        try:
            del MjpgClient.clients[self._camera_id]
            
            logging.debug('mjpg client on port %(port)s removed' % {'port': self._port})
            
        except KeyError:
            pass
        
        iostream.IOStream.close(self)
    
    def _check_error(self):
        if self.error is None:
            return False
        
        self._error(self.error)
        
        return True
     
    def _error(self, error):
        logging.error('mjpg client error: %(msg)s' % {
                'msg': unicode(error)})
        
        try:
            self.close()
        
        except:
            pass
    
    def _on_connect(self):
        logging.debug('mjpg client connected on port %(port)s...' % {'port': self._port})
        
        self.write(b"GET / HTTP/1.0\r\n\r\n")
        self._seek_content_length()
        
    def _seek_content_length(self):
        if self._check_error():
            return
        
        self.read_until('Content-Length:', self._on_before_content_length)
    
    def _on_before_content_length(self, data):
        if self._check_error():
            return
        
        self.read_until('\r\n\r\n', self._on_content_length)
    
    def _on_content_length(self, data):
        if self._check_error():
            return
        
        matches = re.findall('(\d+)', data)
        if not matches:
            self._error('could not find content length in mjpg header line "%(header)s"' % {
                    'header': data})
            
            return
        
        length = int(matches[0])
        
        self.read_bytes(length, self._on_jpg)
    
    def _on_jpg(self, data):
        MjpgClient.last_jpgs[self._camera_id] = data
        self._seek_content_length()


def get_jpg(camera_id):
    if camera_id not in MjpgClient.clients:
        # TODO implement some kind of timeout before retry here
        logging.debug('creating mjpg client for camera id %(camera_id)s' % {
                'camera_id': camera_id})
        
        camera_config = config.get_camera(camera_id)
        if not camera_config['@enabled'] or camera_config['@proto'] != 'v4l2':
            logging.error('could not start mjpg client for camera id %(camera_id)s: not enabled or not local' % {
                    'camera_id': camera_id})
            
            return None
        
        port = camera_config['webcam_port']
        client = MjpgClient(camera_id, port)
        client.connect()
        
        return None

    return MjpgClient.last_jpgs.get(camera_id)
