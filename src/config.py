
import errno
import logging
import os.path
import re

from collections import OrderedDict

import settings


_CONFIG_DIR = 'conf'
_CAMERA_CONFIG_FILE_NAME = 'thread-%(id)s.conf'

_MAIN_CONFIG_FILE_PATH = os.path.join(_CONFIG_DIR, 'motion.conf')
_CAMERA_CONFIG_FILE_PATH = os.path.join(_CONFIG_DIR, _CAMERA_CONFIG_FILE_NAME)


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
    config_path = os.path.join(settings.PROJECT_PATH, _CONFIG_DIR)
    
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
    main_config = get_main()
    threads = main_config.get('thread', [])
    data['@enabled'] = _CAMERA_CONFIG_FILE_NAME % {'id': camera_id} in threads
    
    _set_default_motion_camera(data)
    
    return data


def set_camera(camera_id, data):
    # TODO use a cache
    
    _set_default_motion_camera(data)
    
    # set the enabled status in main config
    main_config = get_main()
    threads = main_config.setdefault('thread', [])
    config_file_name = _CAMERA_CONFIG_FILE_NAME % {'id': camera_id}
    if data['@enabled'] and config_file_name not in threads:
        threads.append(config_file_name)
            
    elif not data['@enabled']:
        threads = [t for t in threads if t != config_file_name]

    if len(threads):
        main_config['thread'] = threads
    
    elif 'thread' in main_config:
        del main_config['thread']
    
    set_main(main_config)

    del data['@enabled']
    
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


def add_camera(device):
    # TODO use a cache
    
    # determine the last camera id
    camera_ids = get_camera_ids()

    camera_id = 1
    while camera_id in camera_ids:
        camera_id += 1
    
    logging.info('adding new camera with id %(id)s...' % {'id': camera_id})
    
    # get device type
    proto = None
    if device.count('://'):
        proto, device = device.split('://', 1)

    # add the default camera config
    data = OrderedDict()
    data['@name'] = 'Camera' + str(camera_id)
    data['@proto'] = proto
    data['videodevice'] = device
    
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
    
    if len(threads):
        main_config['thread'] = threads
    
    elif 'thread' in main_config:
        del main_config['thread']

    set_main(main_config)
    
    logging.info('removing camera config file %(path)s...' % {'path': camera_config_path})
    
    try:
        os.remove(camera_config_path)
    
    except Exception as e:
        logging.error('could not remove camera config file %(path)s: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        raise


def camera_ui_to_dict(camera_id, ui):
    video_device = ui.get('device', '')
    if video_device.count('://'):
        video_device = video_device.split('://')[-1]

    data = {
        # device
        '@name': ui.get('name', ''),
        '@enabled': ui.get('enabled', False),
        'videodevice': video_device,
        'lightswitch': int(ui.get('light_switch_detect', False) * 5),
        'auto_brightness': ui.get('auto_brightness', False),
        'brightness': int(int(ui.get('brightness', 0)) * 2.55),
        'contrast': int(int(ui.get('contrast', 0)) * 2.55),
        'saturation': int(int(ui.get('saturation', 0)) * 2.55),
        'hue': int(int(ui.get('hue', 0))),
        'width': int(ui.get('resolution', '352x288').split('x')[0]),
        'height': int(ui.get('resolution', '352x288').split('x')[1]),
        'framerate': int(ui.get('framerate', 1)),
        
        # file storage
        '@storage_device': ui.get('storage_device', 'local-disk'),
        '@network_server': ui.get('network_server', ''),
        '@network_share_name': ui.get('network_share_name', ''),
        '@network_username': ui.get('network_username', ''),
        '@network_password': ui.get('network_password', ''),
        'target_dir': ui.get('root_directory', '/'),
        
        # text overlay
        'text_left': '',
        'text_right': '',
        
        # streaming
        'webcam_localhost': not ui.get('video_streaming', True),
        'webcam_port': int(ui.get('streaming_port', 8080)),
        'webcam_maxrate': int(ui.get('streaming_framerate', 1)),
        'webcam_quality': max(1, int(ui.get('streaming_quality', 50))),
        
        # still images
        'output_normal': False,
        'output_all': False,
        'output_motion': False,
        'snapshot_interval': 0,
        'jpeg_filename': '',
        'snapshot_filename': '',
        # TODO preserve images
        
        # movies
        'ffmpeg_variable_bitrate': 0,
        'ffmpeg_video_codec': 'mpeg4',
        'ffmpeg_cap_new': True,
        'movie_filename': '',
        # TODO preserve movies
    
        # motion detection
        'text_changes': ui.get('show_frame_changes', False),
        'locate': ui.get('show_frame_changes', False),
        'threshold': ui.get('frame_change_threshold', 1500),
        'noise_tune': ui.get('auto_noise_detect', True),
        'noise_level': max(1, int(int(ui.get('noise_level', 8)) * 2.55)),
        'gap': int(ui.get('gap', 60)),
        'pre_capture': int(ui.get('pre_capture', 0)),
        'post_capture': int(ui.get('post_capture', 0)),
        
        # TODO notifications
    }
    
    if ui.get('text_overlay', False):
        left_text = ui.get('left_text', 'camera-name')
        if left_text == 'camera-name':
            data['text_left'] = ui.get('name')
            
        elif left_text == 'timestamp':
            data['text_left'] = '%Y-%m-%d\n%T'
            
        else:
            data['text_left'] = ui.get('custom_left_text', '')
        
        right_text = ui.get('right_text', 'timestamp')
        if right_text == 'camera-name':
            data['text_right'] = ui.get('name')
            
        elif right_text == 'timestamp':
            data['text_right'] = '%Y-%m-%d\n%T'
            
        else:
            data['text_right'] = ui.get('custom_right_text', '')

    if ui.get('still_images', False):
        capture_mode = ui.get('capture_mode', 'motion-triggered')
        if capture_mode == 'motion-triggered':
            data['output_normal'] = True
            data['jpeg_filename'] = ui.get('image_file_name', '%Y-%m-%d-%H-%M-%S-%q')  
            
        elif capture_mode == 'interval-snapshots':
            data['snapshot_interval'] = int(ui.get('snapshot_interval'), 300)
            data['snapshot_filename'] = ui.get('image_file_name', '%Y-%m-%d-%H-%M-%S-%q')
            
        elif capture_mode == 'all-frames':
            data['output_all'] = True
            data['jpeg_filename'] = ui.get('image_file_name', '%Y-%m-%d-%H-%M-%S')
            
        data['quality'] = max(1, int(ui.get('image_quality', 75)))
        
    if ui.get('motion_movies', False):
        data['ffmpeg_variable_bitrate'] = 2 + int((100 - int(ui.get('movie_quality', 50))) * 0.29)
        data['movie_filename'] = ui.get('movie_file_name', '%Y-%m-%d-%H-%M-%S-%q')

    return data
    

def camera_dict_to_ui(camera_id, data):
    # set the default options if not present
    _set_default_motion_camera(data)
    
    ui = {
        # device
        'name': data['@name'],
        'enabled': data['@enabled'],
        'device': 'v4l2://' + data['videodevice'],
        'light_switch_detect': data['lightswitch'] > 0,
        'auto_brightness': data['auto_brightness'],
        'brightness': int(int(data['brightness']) / 2.55),
        'contrast': int(int(data['contrast']) / 2.55),
        'saturation': int(int(data['saturation']) / 2.55),
        'hue': int(int(data['hue'])),
        'resolution': str(data['width']) + 'x' + str(data['height']),
        'framerate': int(data['framerate']),
        
        # file storage
        'storage_device': data['@storage_device'],
        'network_server': data['@network_server'],
        'network_share_name': data['@network_share_name'],
        'network_username': data['@network_username'],
        'network_password': data['@network_password'],
        'root_directory': data['target_dir'],
        
        # text overlay
        'text_overlay': False,
        'left_text': 'camera-name',
        'right_text': 'timestamp',
        
        # streaming
        'vudeo_streaming': not data['webcam_localhost'],
        'streaming_port': int(data['webcam_port']),
        'streaming_framerate': int(data['webcam_maxrate']),
        'streaming_quality': int(data['webcam_quality']),
        
        # still images
        'still_images': False,
        'capture_mode': 'motion-triggered',
        'image_file_name': '%Y-%m-%d-%H-%M-%S',
        'image_quality': 75,
        # TODO preserve images
        
        # motion movies
        'motion_movies': False,
        'movie_quality': 50,
        'movie_file_name': '%Y-%m-%d-%H-%M-%S-%q',
        # TODO preserve movies
        
        # motion detection
        'show_frame_changes': data.get('text_changes') or data.get('locate'),
        'frame_change_threshold': data['threshold'],
        'auto_noise_detect': data['noise_tune'],
        'noise_level': int(int(data['noise_level']) / 2.55),
        'gap': int(data['gap']),
        'pre_capture': int(data['pre_capture']),
        'post_capture': int(data['post_capture']),
        
        # TODO notifications
    }
    
    text_left = data['text_left']
    text_right = data['text_right'] 
    if text_left or text_right:
        ui['text_overlay'] = True
        
        if text_left == data['@name']:
            ui['left_text'] = 'camera-name'
            
        elif text_left == '%Y-%m-%d\n%T':
            ui['left_text'] = 'timestamp'
            
        else:
            ui['left_text'] = 'custom-text'
            ui['custom_left_text'] = text_left

        if text_right == data['@name']:
            ui['right_text'] = 'camera-name'
            
        elif text_right == '%Y-%m-%d\n%T':
            ui['right_text'] = 'timestamp'
            
        else:
            ui['right_text'] = 'custom-text'
            ui['custom_right_text'] = text_right

    output_all = data.get('output_all')
    output_normal = data.get('output_normal')
    jpeg_filename = data.get('jpeg_filename')
    snapshot_interval = data.get('snapshot_interval')
    snapshot_filename = data.get('snapshot_filename')
    
    if (((output_all or output_normal) and jpeg_filename) or
        (snapshot_interval and snapshot_filename)):
        
        ui['still_images'] = True
        
        if output_all:
            ui['capture_mode'] = 'all-frames'
            ui['image_file_name'] = jpeg_filename
            
        elif data.get('snapshot_interval'):
            ui['capture-mode'] = 'interval-snapshots'
            ui['image_file_name'] = snapshot_filename
            
        elif data.get('output_normal'):
            ui['capture-mode'] = 'motion-triggered'
            ui['image_file_name'] = jpeg_filename  
            
        ui['image_quality'] = ui.get('quality', 75)
    
    movie_filename = data.get('movie_filename')
    if movie_filename:
        ui['motion_movies'] = True
        ui['movie_quality'] = int((max(2, data['ffmpeg_variable_bitrate']) - 2) / 0.29)
        ui['movie_file_name'] = movie_filename
    
    return data
    

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
    data.setdefault('videodevice', '')
    data.setdefault('lightswitch', 0)
    data.setdefault('auto_brightness', False)
    data.setdefault('brightness', 0)
    data.setdefault('contrast', 0)
    data.setdefault('saturation', 0)
    data.setdefault('hue', 0)
    data.setdefault('width', 352)
    data.setdefault('height', 288)
    data.setdefault('framerate', 1)
    
    data.setdefault('@storage_device', 'local-disk')
    data.setdefault('@network_server', '')
    data.setdefault('@network_share_name', '')
    data.setdefault('@network_username', '')
    data.setdefault('@network_password', '')
    data.setdefault('target_dir', '.')
    
    data.setdefault('webcam_localhost', False)
    data.setdefault('webcam_port', 8080)
    data.setdefault('webcam_maxrate', 1)
    data.setdefault('webcam_quality', 50)
    
    data.setdefault('text_left', '')
    data.setdefault('text_right', '')

    data.setdefault('text_changes', False)
    data.setdefault('locate', False)
    data.setdefault('threshold', 1500)
    data.setdefault('noise_tune', True)
    data.setdefault('noise_level', 32)
    
    data.setdefault('gap', 60)
    data.setdefault('pre_capture', 0)
    data.setdefault('post_capture', 0)
    
    data.setdefault('output_all', False)
    data.setdefault('output_normal', False)
    data.setdefault('jpeg_filename', '')
    data.setdefault('snapshot_interval', 0)
    data.setdefault('snapshot_filename', '')
    data.setdefault('quality', 75)
    
    data.setdefault('movie_filename', '')
    data.setdefault('ffmpeg_variable_bitrate', 14)
