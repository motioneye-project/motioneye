
import errno
import os.path
import signal
import subprocess
import time

import settings


def find_program():
    try:
        return subprocess.check_output('which motion', shell=True).strip()
    
    except subprocess.CalledProcessError: # not found
        return None


def start():
    if running():
        raise Exception('motion is already running')

    program = find_program()
    if not program:
        raise Exception('motion executable could not be found')
    
    motion_config_path = os.path.join(settings.CONF_PATH, 'motion.conf')
    motion_log_path = os.path.join(settings.RUN_PATH, 'motion.log')
    motion_pid_path = os.path.join(settings.RUN_PATH, 'motion.pid')
    
    args = [program,
            '-c', motion_config_path,
            '-n']

    log_file = open(motion_log_path, 'w')
    
    process = subprocess.Popen(args, stdout=log_file, stderr=log_file, close_fds=True,
            cwd=settings.CONF_PATH)
    
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
    if not running():
        raise Exception('motion is not running')
    
    pid = _get_pid()
    if pid is not None:
        try:
            # send the TERM signal once
            os.kill(pid, signal.SIGTERM)
            
            # wait 5 seconds for the process to exit
            for i in xrange(50):  # @UnusedVariable
                time.sleep(0.1)
                os.kill(pid, 0)
            
            # send the KILL signal once
            os.kill(pid, signal.SIGKILL)
            
            # wait 2 seconds for the process to exit
            for i in xrange(20):  # @UnusedVariable
                time.sleep(0.1)
                os.kill(pid, 0)
                
            # the process still did not exit
            raise Exception('could not terminate the motion process')
        
        except OSError as e:
            if e.errno != errno.ESRCH:
                raise
    

def running():
    pid = _get_pid()
    if pid is None:
        return False
    
    try:
        os.kill(pid, 0)
        
        # the process is running
        return True
    
    except OSError as e:
        if e.errno != errno.ESRCH:
            raise

    return False


def _get_pid():
    motion_pid_path = os.path.join(settings.RUN_PATH, 'motion.pid')
    
    # read the pid from file
    try:
        with open(motion_pid_path, 'r') as f:
            return int(f.readline().strip())
        
    except IOError, ValueError:
        return None
