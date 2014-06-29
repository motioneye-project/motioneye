
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

import config
import settings


_started = False


def find_motion():
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
    
    return (binary, version)


def start():
    global _started
    
    _started = True
    
    if running() or not config.has_enabled_cameras():
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
            '-n']

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
            if e.errno != errno.ECHILD:
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


def _get_pid():
    motion_pid_path = os.path.join(settings.RUN_PATH, 'motion.pid')
    
    # read the pid from file
    try:
        with open(motion_pid_path, 'r') as f:
            return int(f.readline().strip())
        
    except (IOError, ValueError):
        return None
