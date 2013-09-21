
import errno
import json
import logging
import os.path
import re

import settings


_CONFIG_DIR = 'conf'
_CAMERA_CONFIG_FILE_NAME = 'thread-%(id)s.conf'

_GENERAL_CONFIG_FILE_PATH = os.path.join(_CONFIG_DIR, 'motion-eye.json')
_MOTION_CONFIG_FILE_PATH = os.path.join(_CONFIG_DIR, 'motion.conf')
_CAMERA_CONFIG_FILE_PATH = os.path.join(_CONFIG_DIR, _CAMERA_CONFIG_FILE_NAME)


def get_general():
    config_file_path = os.path.join(settings.PROJECT_PATH, _GENERAL_CONFIG_FILE_PATH)
    
    logging.info('reading general config from file %(path)s...' % {'path': config_file_path})
    
    try:
        file = open(config_file_path, 'r')
    
    except IOError as e:
        if e.errno == errno.ENOENT:  # file does not exist
            logging.info('config file %(path)s does not exist, creating a new default one...' % {'path': config_file_path})
            
            return set_general({})
        
        else:
            logging.error('could not open config file %(path)s: %(msg)s' % {
                    'path': config_file_path, 'msg': unicode(e)})
            
            return None
    
    try:
        data = json.load(file)
        _set_default_general(data)
        
        return data
    
    except Exception as e:
        logging.error('could not read config file %(path)s: %(msg)s' % {
                'path': config_file_path, 'msg': unicode(e)})
        
    finally:
        file.close()
        
    return None


def set_general(data):
    _set_default_general(data)

    config_file_path = os.path.join(settings.PROJECT_PATH, _GENERAL_CONFIG_FILE_PATH)
    
    logging.info('writing general config to file %(path)s...' % {'path': config_file_path})
    
    try:
        file = open(config_file_path, 'w')
    
    except Exception as e:
        logging.error('could not open config file %(path)s for writing: %(msg)s' % {
                'path': config_file_path, 'msg': unicode(e)})
        
        return None
    
    try:
        json.dump(file, data)
    
    except Exception as e:
        logging.error('could not write config file %(path)s: %(msg)s' % {
                'path': config_file_path, 'msg': unicode(e)})
        
    finally:
        file.close()
        
    return data


def get_cameras():
    config_path = os.path.join(settings.PROJECT_PATH, _CONFIG_DIR)
    
    logging.info('loading cameras from directory %(path)s...' % {'path': config_path})
    
    try:
        ls = os.listdir(config_path)
        
    except Exception as e:
        logging.error('could not list contents of %(dir)s: %(msg)s' % {
                'dir': config_path, 'msg': unicode(e)})
        
        return None
    
    cameras = {}
    
    pattern = _CAMERA_CONFIG_FILE_NAME.replace('%(id)s', '(\w+)')
    for name in ls:
        match = re.match(pattern, name)
        if not match:
            continue # not a camera config file
        
        camera_id = match.groups()[0]
        
        camera_config_path = os.path.join(config_path, name)
        
        logging.info('reading camera config from %(path)s...' % {'path': camera_config_path})
        
        try:
            file = open(camera_config_path, 'r')
        
        except Exception as e:
            logging.error('could not open camera config file %(path)s: %(msg)s' % {
                    'path': camera_config_path, 'msg': unicode(e)})
            
            continue
        
        try:
            lines = [l[:-1] for l in file.readlines()]
        
        except Exception as e:
            logging.error('could not read camera config file %(path)s: %(msg)s' % {
                    'path': camera_config_path, 'msg': unicode(e)})
            
            continue
        
        finally:
            file.close()
        
        data = _conf_to_dict(lines)
        _set_default_motion_camera(data)
        
        cameras[camera_id] = data
        
    logging.info('loaded %(count)d cameras' % {'count': len(cameras)})
    
    return cameras
        

def get_camera(camera_id):
    config_path = os.path.join(settings.PROJECT_PATH, _CONFIG_DIR)
    camera_config_path = os.path.join(config_path, _CAMERA_CONFIG_FILE_NAME % {'id': camera_id})
    
    logging.info('reading camera config from %(path)s...' % {'path': camera_config_path})
    
    try:
        file = open(camera_config_path, 'r')
    
    except Exception as e:
        logging.error('could not open camera config file: %(msg)s' % {'msg': unicode(e)})
        
        return None
    
    try:
        lines = [l[:-1] for l in file.readlines()]
    
    except Exception as e:
        logging.error('could not read camera config file %(path)s: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        return None
    
    finally:
        file.close()
    
    data = _conf_to_dict(lines)
    _set_default_motion_camera(data)
    
    return data


def set_camera(camera_id, data):
    config_path = os.path.join(settings.PROJECT_PATH, _CONFIG_DIR)
    camera_config_path = os.path.join(config_path, _CAMERA_CONFIG_FILE_NAME % {'id': camera_id})
    
    # read the actual configuration from file
    
    logging.info('reading camera config from %(path)s...' % {'path': camera_config_path})
    
    try:
        file = open(camera_config_path, 'r')
    
    except Exception as e:
        logging.error('could not open camera config file %(path)s: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        return None
    
    try:
        lines = [l[:-1] for l in file.readlines()]
    
    except Exception as e:
        logging.error('could not read camera config file %(path)s: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        return None
    
    finally:
        file.close()
    
    # write the configuration to file
    
    logging.info('writing camera config to %(path)s...' % {'path': camera_config_path})
    
    try:
        file = open(camera_config_path, 'w')
    
    except Exception as e:
        logging.error('could not open camera config file %(path)s for writing: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        return None
    
    lines = _dict_to_conf(lines, data)
    
    try:
        file.writelines([l + '\n' for l in lines])
    
    except Exception as e:
        logging.error('could not write camera config file %(path)s: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        return None
    
    finally:
        file.close()
    
    return data


def add_camera():
    config_path = os.path.join(settings.PROJECT_PATH, _CONFIG_DIR)
    
    logging.info('loading cameras from directory %(path)s...' % {'path': config_path})
    
    try:
        ls = os.listdir(config_path)
        
    except Exception as e:
        logging.error('could not list contents of %(dir)s: %(msg)s' % {
                'dir': config_path, 'msg': unicode(e)})
        
        return None
    
    camera_ids = []
    
    pattern = _CAMERA_CONFIG_FILE_NAME.replace('%(id)s', '(\w+)')
    for name in ls:
        match = re.match(pattern, name)
        if not match:
            continue # not a camera config file
        
        camera_id = match.groups()[0]
        try:
            camera_id = int(camera_id)
        
        except ValueError:
            logging.error('camera id is not an integer: %(id)s' % {'id': camera_id})
            
            continue
            
        camera_ids.append(camera_id)
        
        logging.debug('found camera with id %(id)s' % {'id': camera_id})
    
    last_camera_id = max(camera_ids or [0])
    camera_id = last_camera_id + 1
    
    logging.info('adding new camera with id %(id)s...' % {'id': camera_id})
        
    # write the configuration to file
    
    camera_config_path = os.path.join(config_path, _CAMERA_CONFIG_FILE_NAME % {'id': camera_id})
    logging.info('writing camera config to %(path)s...' % {'path': camera_config_path})
    
    try:
        file = open(camera_config_path, 'w')
    
    except Exception as e:
        logging.error('could not open camera config file %(path)s for writing: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        return None
    
    data = {}
    _set_default_motion_camera(data)
    
    lines = _dict_to_conf([], data)
    
    try:
        file.writelines([l + '\n' for l in lines])
    
    except Exception as e:
        logging.error('could not write camera config file %(path)s: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        return None
    
    finally:
        file.close()
    
    return camera_id, data


def rem_camera(camera_id):
    config_path = os.path.join(settings.PROJECT_PATH, _CONFIG_DIR)
    camera_config_path = os.path.join(config_path, _CAMERA_CONFIG_FILE_NAME % {'id': camera_id})
    
    logging.info('removing camera config file %(path)s...' % {'path': camera_config_path})
    
    try:
        os.remove(camera_config_path)
    
    except Exception as e:
        logging.error('could not remove camera config file %(path)s: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        return None
    

def _value_to_python(value):
    value_lower = value.lower()
    if value_lower == 'off':
        return False
    
    elif value_lower == 'on':
        return True
    
    try:
        return int(value)
    
    except ValueError:
        try:
            return float(value)
        
        except ValueError:
            return value


def _python_to_value(value):
    if value is True:
        return 'on'
    
    elif value is False:
        return 'off'
    
    elif isinstance(value, (int, float)):
        return str(value)
    
    else:
        return value


def _conf_to_dict(lines):
    data = {}
    
    for line in lines:
        line = line.strip()
        if len(line) == 0:  # empty line
            continue
        
        if line.startswith('#') or line.startswith(';'):  # comment line
            continue
        
        parts = line.split(None, 1)
        if len(parts) != 2:  # invalid line format
            continue
        
        (name, value) = parts
        value = value.strip()
        
        value = data[name] = _value_to_python(value)
    
    return data


def _dict_to_conf(lines, data):
    conf_lines = []
    data_copy = dict(data)
    
    # parse existing lines and replace the values
    
    for line in lines:
        line = line.strip()
        if len(line) == 0:  # empty line
            conf_lines.append(line)
            continue
        
        if line.startswith('#') or line.startswith(';'):  # comment line
            conf_lines.append(line)
            continue
        
        parts = line.split(None, 1)
        if len(parts) != 2:  # invalid line format
            conf_lines.append(line)
            continue
        
        (name, value) = parts
        
        new_value = data.get(name)
        if new_value is not None:
            value = _python_to_value(new_value)
            
        line = name + ' ' + value
        conf_lines.append(line)
        
        del data_copy[name]
    
    # add the remaining config values not covered by existing lines
    
    for (name, value) in data_copy:
        line = name + ' ' + value
        conf_lines.append(line)
        
    return conf_lines


def _set_default_general(data):
    data.set_default('show_advanced', False)
    data.set_default('admin_username', 'admin')
    data.set_default('admin_password', '')
    data.set_default('normal_username', 'user')
    data.set_default('storage_device', 'local-disk')
    data.set_default('root_directory', '/')


def _set_default_motion(data):
    pass


def _set_default_motion_camera(data):
    pass
