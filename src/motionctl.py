
import os.path
import subprocess

import settings


def find_program():
    try:
        return subprocess.check_output('which motion', shell=True)
    
    except subprocess.CalledProcessError: # not found
        return None


def start():
    program = find_program()
    if not program:
        raise Exception('motion executable could not be found')
    
    motion_config_path = os.path.join(settings.CONF_PATH, 'motion.conf')
    motion_log_path = os.path.join(settings.RUN_PATH, 'motion.log')
    motion_pid_path = os.path.join(settings.RUN_PATH, 'motion.pid')
    
    args = [program,
        '-c', motion_config_path,
        '-n',
        '-p', motion_pid_path]
    
    log_file = open(motion_log_path, 'w')
    
    subprocess.Popen(args, stdout=log_file, stderr=log_file)


def stop():
    pass


def running():
    pass
