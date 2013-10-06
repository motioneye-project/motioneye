
import errno
import logging
import os.path
import re

from collections import OrderedDict

import settings


_CAMERA_CONFIG_FILE_NAME = 'thread-%(id)s.conf'

_MAIN_CONFIG_FILE_PATH = os.path.join(settings.CONF_PATH, 'motion.conf')
_CAMERA_CONFIG_FILE_PATH = os.path.join(settings.CONF_PATH, _CAMERA_CONFIG_FILE_NAME)


def get_main(as_lines=False):
    # TODO use a cache
    
    config_file_path = os.path.join(settings.PROJECT_PATH, _MAIN_CONFIG_FILE_PATH)
    
    logging.debug('reading main config from file %(path)s...' % {'path': config_file_path})
    
    lines = None
    try:
        file = open(config_file_path, 'r')
    
    except IOError as e:
        if e.errno == errno.ENOENT:  # file does not exist
            logging.info('main config file %(path)s does not exist, using default values' % {'path': config_file_path})
            
            lines = []
        
        else:
            logging.error('could not open main config file %(path)s: %(msg)s' % {
                    'path': config_file_path, 'msg': unicode(e)})
            
            raise
    
    if lines is None:
        try:
            lines = [l[:-1] for l in file.readlines()]
        
        except Exception as e:
            logging.error('could not read main config file %(path)s: %(msg)s' % {
                    'path': _MAIN_CONFIG_FILE_PATH, 'msg': unicode(e)})
            
            raise
        
        finally:
            file.close()
    
    if as_lines:
        return lines
    
    data = _conf_to_dict(lines, list_names=['thread'])
    _set_default_motion(data)
    
    return data
        

def set_main(data):
    # TODO use a cache
    
    _set_default_motion(data)
    
    # read the actual configuration from file
    lines = get_main(as_lines=True)
    
    # preserve the threads
    if 'thread' not in data:
        threads = data.setdefault('thread', [])
        for line in lines:
            match = re.match('^\s*thread\s+([a-zA-Z0-9.\-]+)', line)
            if match:
                threads.append(match.groups()[0])
    
    # write the configuration to file
    logging.debug('writing main config to %(path)s...' % {'path': _MAIN_CONFIG_FILE_PATH})
    
    try:
        file = open(_MAIN_CONFIG_FILE_PATH, 'w')
    
    except Exception as e:
        logging.error('could not open main config file %(path)s for writing: %(msg)s' % {
                'path': _MAIN_CONFIG_FILE_PATH, 'msg': unicode(e)})
        
        raise
    
    lines = _dict_to_conf(lines, data, list_names=['thread'])
    
    try:
        file.writelines([l + '\n' for l in lines])
    
    except Exception as e:
        logging.error('could not write main config file %(path)s: %(msg)s' % {
                'path': _MAIN_CONFIG_FILE_PATH, 'msg': unicode(e)})
        
        raise
    
    finally:
        file.close()
    
    return data


def get_camera_ids():
    config_path = settings.CONF_PATH
    
    logging.debug('listing config dir %(path)s...' % {'path': config_path})
    
    try:
        ls = os.listdir(config_path)
    
    except Exception as e:
        logging.error('failed to list config dir %(path)s: %(msg)s', {
                'path': config_path, 'msg': unicode(e)})
        
        raise
    
    camera_ids = []
    
    pattern = _CAMERA_CONFIG_FILE_NAME.replace('%(id)s', '(\d+)')
    for name in ls:
        match = re.match(pattern, name)
        if match:
            camera_id = int(match.groups()[0])
            logging.debug('found camera with id %(id)s' % {
                    'id': camera_id})
            
            camera_ids.append(camera_id)
        
    camera_ids.sort()
    
    return camera_ids


def has_enabled_cameras():
    if not get_main().get('@enabled'):
        return False
    
    camera_ids = get_camera_ids()
    cameras = [get_camera(camera_id) for camera_id in camera_ids]
    return bool([c for c in cameras if c['@enabled'] and c['@proto'] == 'v4l2'])


def get_camera(camera_id, as_lines=False):
    # TODO use a cache
    
    camera_config_path = _CAMERA_CONFIG_FILE_PATH % {'id': camera_id}
    
    logging.debug('reading camera config from %(path)s...' % {'path': camera_config_path})
    
    try:
        file = open(camera_config_path, 'r')
    
    except Exception as e:
        logging.error('could not open camera config file: %(msg)s' % {'msg': unicode(e)})
        
        raise
    
    try:
        lines = [l[:-1] for l in file.readlines()]
    
    except Exception as e:
        logging.error('could not read camera config file %(path)s: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        raise
    
    finally:
        file.close()
    
    if as_lines:
        return lines
        
    data = _conf_to_dict(lines)
    
    # determine the enabled status
    if data['@proto'] == 'v4l2':
        main_config = get_main()
        threads = main_config.get('thread', [])
        data['@enabled'] = _CAMERA_CONFIG_FILE_NAME % {'id': camera_id} in threads
        data['@id'] = camera_id

        _set_default_motion_camera(data)
    
    return data


def set_camera(camera_id, data):
    # TODO use a cache
    
    if data['@proto'] == 'v4l2':
        _set_default_motion_camera(data)
        
        # set the enabled status in main config
        main_config = get_main()
        threads = main_config.setdefault('thread', [])
        config_file_name = _CAMERA_CONFIG_FILE_NAME % {'id': camera_id}
        if data['@enabled'] and config_file_name not in threads:
            threads.append(config_file_name)
                
        elif not data['@enabled']:
            threads = [t for t in threads if t != config_file_name]
    
        main_config['thread'] = threads
        
        if '@id' in data:
            del data['@id']
        
        set_main(main_config)

    # read the actual configuration from file
    config_file_path = _CAMERA_CONFIG_FILE_PATH % {'id': camera_id}
    if os.path.isfile(config_file_path):
        lines = get_camera(camera_id, as_lines=True)
    
    else:
        lines = []
    
    # write the configuration to file
    camera_config_path = _CAMERA_CONFIG_FILE_PATH % {'id': camera_id}
    logging.debug('writing camera config to %(path)s...' % {'path': camera_config_path})
    
    try:
        file = open(camera_config_path, 'w')
    
    except Exception as e:
        logging.error('could not open camera config file %(path)s for writing: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        raise
    
    lines = _dict_to_conf(lines, data)
    
    try:
        file.writelines([l + '\n' for l in lines])
    
    except Exception as e:
        logging.error('could not write camera config file %(path)s: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        raise
    
    finally:
        file.close()
    
    return data


def add_camera(device_details):
    # TODO use a cache
    
    # determine the last camera id
    camera_ids = get_camera_ids()

    camera_id = 1
    while camera_id in camera_ids:
        camera_id += 1
    
    logging.info('adding new camera with id %(id)s...' % {'id': camera_id})
    
    # add the default camera config
    proto = device_details['proto']
        
    data = OrderedDict()
    data['@proto'] = proto
    data['@enabled'] = device_details.get('enabled', True)
    
    if proto == 'v4l2':
        data['@name'] = 'Camera' + str(camera_id)
        data['videodevice'] = device_details['device']
        if 'width' in device_details:
            data['width'] = device_details['width']
            data['height'] = device_details['height']
        
    else:
        data['@host'] = device_details['host']
        data['@port'] = device_details['port']
        data['@username'] = device_details['username']
        data['@password'] = device_details['password']
        data['@remote_camera_id'] = device_details['remote_camera_id']
        data['@enabled'] = device_details.get('enabled', True)

    # write the configuration to file
    set_camera(camera_id, data)
    
    return camera_id, data


def rem_camera(camera_id):
    # TODO use a cache

    camera_config_name = _CAMERA_CONFIG_FILE_NAME % {'id': camera_id}
    camera_config_path = _CAMERA_CONFIG_FILE_PATH % {'id': camera_id}
    
    # remove the camera from the main config
    main_config = get_main()
    threads = main_config.setdefault('thread', [])
    threads = [t for t in threads if t != camera_config_name]
    
    main_config['thread'] = threads

    set_main(main_config)
    
    logging.info('removing camera config file %(path)s...' % {'path': camera_config_path})
    
    try:
        os.remove(camera_config_path)
    
    except Exception as e:
        logging.error('could not remove camera config file %(path)s: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        raise


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


def _conf_to_dict(lines, list_names=[]):
    data = OrderedDict()
    
    for line in lines:
        line = line.strip()
        if len(line) == 0:  # empty line
            continue
        
        if line.startswith(';'):  # comment line
            continue
        
        match = re.match('^\#\s*(\@\w+)\s*([^\#]*)', line)
        if match:
            name, value = match.groups()[:2]
        
        elif line.startswith('#'): # comment line
            continue

        else:
            line = line.split('#')[0] # everything up to the first #
            
            parts = line.split(None, 1)
            if len(parts) != 2:  # invalid line format
                continue

            (name, value) = parts
            value = value.strip()
        
        value = _value_to_python(value)
        
        if name in list_names:
            data.setdefault(name, []).append(value)
        
        else:
            data[name] = value

    return data


def _dict_to_conf(lines, data, list_names=[]):
    conf_lines = []
    data_copy = OrderedDict(data)
    
    # parse existing lines and replace the values
    
    for line in lines:
        line = line.strip()
        if len(line) == 0:  # empty line
            conf_lines.append(line)
            continue

        if line.startswith(';'):  # comment line
            continue
        
        match = re.match('^\#\s*(\@\w+)\s*([^\#]*)', line)
        if match: # @line
            (name, value) = match.groups()[:2]
        
        elif line.startswith('#'):  # comment line
            conf_lines.append(line)
            continue
        
        else:
            parts = line.split(None, 1)
            if len(parts) == 2:
                (name, value) = parts
            
            else:
                (name, value) = parts[0], ''
        
        if name not in data_copy:
            continue # name already processed
        
        if name in list_names:
            new_value = data.get(name)
            if new_value is not None:
                for v in new_value:
                    line = name + ' ' + _python_to_value(v)
                    conf_lines.append(line)
            
            else:
                line = name + ' ' + value
                conf_lines.append(line)

        else:
            new_value = data.get(name)
            if new_value is not None:
                value = _python_to_value(new_value)
            
            line = name + ' ' + value
            conf_lines.append(line)
        
        del data_copy[name]
    
    # add the remaining config values not covered by existing lines
    
    if len(data_copy) and len(lines):
        conf_lines.append('') # add a blank line
    
    for (name, value) in data_copy.iteritems():
        if name in list_names:
            for v in value:
                line = name + ' ' + _python_to_value(v)
                conf_lines.append(line)

        else:
            line = name + ' ' + _python_to_value(value)
            conf_lines.append(line)
    
    lines = []
    for i, line in enumerate(conf_lines):
        if i > 0 and len(conf_lines[i].strip()) == 0 and len(conf_lines[i - 1].strip()) == 0:
            continue
        
        if line.startswith('@'):
            line = '# ' + line
        
        lines.append(line)
        
    return lines


def _set_default_motion(data):
    data.setdefault('@enabled', True)
    data.setdefault('@show_advanced', False)
    data.setdefault('@admin_username', 'admin')
    data.setdefault('@admin_password', '')
    data.setdefault('@normal_username', 'user')
    data.setdefault('@normal_password', '')


def _set_default_motion_camera(data):
    data.setdefault('@name', '')
    data.setdefault('@enabled', False)
    data.setdefault('@proto', 'v4l2')
    data.setdefault('videodevice', '')
    data.setdefault('lightswitch', 0)
    data.setdefault('auto_brightness', True)
    data.setdefault('brightness', 127)
    data.setdefault('contrast', 127)
    data.setdefault('saturation', 127)
    data.setdefault('hue', 127)
    data.setdefault('width', 352)
    data.setdefault('height', 288)
    data.setdefault('framerate', 5)
    data.setdefault('rotate', 0)
    
    data.setdefault('@storage_device', 'local-disk')
    data.setdefault('@network_server', '')
    data.setdefault('@network_share_name', '')
    data.setdefault('@network_username', '')
    data.setdefault('@network_password', '')
    data.setdefault('target_dir', settings.RUN_PATH)
    
    data.setdefault('webcam_localhost', False)
    data.setdefault('webcam_port', 8080)
    data.setdefault('webcam_maxrate', 5)
    data.setdefault('webcam_quality', 75)
    data.setdefault('webcam_motion', False)
    
    data.setdefault('text_left', data['@name'])
    data.setdefault('text_right', '%Y-%m-%d\\n%T')
    data.setdefault('text_double', False)

    data.setdefault('text_changes', False)
    data.setdefault('locate', False)
    data.setdefault('threshold', 1500)
    data.setdefault('noise_tune', True)
    data.setdefault('noise_level', 32)
    
    data.setdefault('gap', 60)
    data.setdefault('pre_capture', 5)
    data.setdefault('post_capture', 5)
    
    data.setdefault('output_all', False)
    data.setdefault('output_normal', False)
    data.setdefault('jpeg_filename', '')
    data.setdefault('snapshot_interval', 0)
    data.setdefault('snapshot_filename', '')
    data.setdefault('quality', 75)
    data.setdefault('@preserve_images', 0)
    
    data.setdefault('ffmpeg_variable_bitrate', 14)
    data.setdefault('movie_filename', '%Y-%m-%d-%H-%M-%S')
    data.setdefault('ffmpeg_cap_new', False)
    data.setdefault('@preserve_movies', 0)
    
    data.setdefault('@motion_notifications', False)
    data.setdefault('@motion_notifications_emails', '')
    
    data.setdefault('@working_schedule', '')
