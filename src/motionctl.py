
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

import errno
import logging
import os.path
import re
import signal
import subprocess
import time

from tornado.httpclient import HTTPClient, AsyncHTTPClient, HTTPRequest

import config
import settings
import utils


_started = False
_motion_binary_cache = None


def find_motion():
    global _motion_binary_cache
    if _motion_binary_cache:
        return _motion_binary_cache

    try:
        binary = subprocess.check_output('which motion', shell=True).strip()
    
    except subprocess.CalledProcessError: # not found
        return None

    try:
        help = subprocess.check_output(binary + ' -h || true', shell=True)
    
    except subprocess.CalledProcessError: # not found
        return None
    
    result = re.findall('^motion Version ([^,]+)', help)
    version = result and result[0] or ''
    
    _motion_binary_cache = (binary, version)
    
    return _motion_binary_cache


def start():
    global _started
    
    _started = True
    
    if running() or not config.has_local_enabled_cameras():
        return
    
    logging.debug('starting motion')
 
    program = find_motion()
    if not program:
        raise Exception('motion executable could not be found')
    
    program, version = program  # @UnusedVariable
    
    motion_config_path = os.path.join(settings.CONF_PATH, 'motion.conf')
    motion_log_path = os.path.join(settings.RUN_PATH, 'motion.log')
    motion_pid_path = os.path.join(settings.RUN_PATH, 'motion.pid')
    
    args = [program,
            '-c', motion_config_path,
            '-n',
            '-d']
    
    if settings.LOG_LEVEL == logging.DEBUG:
        args.append('9')
    
    else:
        args.append('1')

    log_file = open(motion_log_path, 'w')
    
    process = subprocess.Popen(args, stdout=log_file, stderr=log_file, close_fds=True, cwd=settings.CONF_PATH)
    
    # wait 2 seconds to see that the process has successfully started
    for i in xrange(20):  # @UnusedVariable
        time.sleep(0.1)
        exit_code = process.poll()
        if exit_code is not None and exit_code != 0:
            raise Exception('motion failed to start')

    pid = process.pid
    
    # write the pid to file
    with open(motion_pid_path, 'w') as f:
        f.write(str(pid) + '\n')


def stop():
    import mjpgclient
    
    global _started
    
    _started = False
    
    if not running():
        return
    
    logging.debug('stopping motion')

    mjpgclient.close_all()
    
    pid = _get_pid()
    if pid is not None:
        try:
            # send the TERM signal once
            os.kill(pid, signal.SIGTERM)
            
            # wait 5 seconds for the process to exit
            for i in xrange(50):  # @UnusedVariable
                os.waitpid(pid, os.WNOHANG)
                time.sleep(0.1)

            # send the KILL signal once
            os.kill(pid, signal.SIGKILL)
            
            # wait 2 seconds for the process to exit
            for i in xrange(20):  # @UnusedVariable
                time.sleep(0.1)
                os.waitpid(pid, os.WNOHANG)
                
            # the process still did not exit
            raise Exception('could not terminate the motion process')
        
        except OSError as e:
            if e.errno not in (errno.ESRCH, errno.ECHILD):
                raise
    

def running():
    pid = _get_pid()
    if pid is None:
        return False
    
    try:
        os.waitpid(pid, os.WNOHANG)
        os.kill(pid, 0)
        
        # the process is running
        return True
    
    except OSError as e:
        if e.errno not in (errno.ESRCH, errno.ECHILD):
            raise

    return False


def started():
    return _started


def get_motion_detection(camera_id):
    thread_id = _get_thread_id(camera_id)
    if thread_id is None:
        return logging.error('could not find thread id for camera with id %s' % camera_id)
    
    url = 'http://127.0.0.1:7999/%(id)s/detection/status' % {'id': thread_id}
    
    request = HTTPRequest(url, connect_timeout=2, request_timeout=2)
    http_client = HTTPClient()
    response = http_client.fetch(request)

    if response.error:
        logging.error('failed to get motion detection status for camera with id %(id)s: %(msg)s' % {
                'id': camera_id,
                'msg': unicode(response.error)})
        
        return None
    
    enabled = bool(response.body.lower().count('active'))
    
    logging.debug('motion detection is %(what)s for camera with id %(id)s' % {
            'what': ['disabled', 'enabled'][enabled],
            'id': camera_id})
    
    return enabled


def set_motion_detection(camera_id, enabled):
    thread_id = _get_thread_id(camera_id)
    if thread_id is None:
        return logging.error('could not find thread id for camera with id %s' % camera_id)
    
    logging.debug('%(what)s motion detection for camera with id %(id)s' % {
            'what': ['disabling', 'enabling'][enabled],
            'id': camera_id})
    
    url = 'http://127.0.0.1:7999/%(id)s/detection/%(enabled)s' % {
            'id': thread_id,
            'enabled': ['pause', 'start'][enabled]}
    
    def on_response(response):
        if response.error:
            logging.error('failed to %(what)s motion detection for camera with id %(id)s: %(msg)s' % {
                    'what': ['disable', 'enable'][enabled],
                    'id': camera_id,
                    'msg': unicode(response.error)})
        
        else:
            logging.debug('successfully %(what)s motion detection for camera with id %(id)s' % {
                    'what': ['disabled', 'enabled'][enabled],
                    'id': camera_id})

    request = HTTPRequest(url, connect_timeout=4, request_timeout=4)
    http_client = AsyncHTTPClient()
    http_client.fetch(request, on_response)


def _get_thread_id(camera_id):
    # find the corresponding thread_id
    # (which can be different from camera_id)
    camera_ids = config.get_camera_ids()
    thread_id = 0
    for cid in camera_ids:
        camera_config = config.get_camera(cid)
        if utils.local_camera(camera_config):
            thread_id += 1
        
        if cid == camera_id:
            break
    
    else:
        return None
    
    if thread_id == 0:
        return None
    
    return thread_id


def _get_pid():
    motion_pid_path = os.path.join(settings.RUN_PATH, 'motion.pid')
    
    # read the pid from file
    try:
        with open(motion_pid_path, 'r') as f:
            return int(f.readline().strip())
        
    except (IOError, ValueError):
        return None
