
import errno
import json
import logging
import os.path

import settings


_CONFIG_DIR = 'conf'
_CAMERA_CONFIG_FILE_NAME = 'thread-%(id)s.conf'

_GENERAL_CONFIG_FILE_PATH = os.path.join(_CONFIG_DIR, 'motion-eye.json')
_MOTION_CONFIG_FILE_PATH = os.path.join(_CONFIG_DIR, 'motion.conf')
_CAMERA_CONFIG_FILE_PATH = os.path.join(_CONFIG_DIR, _CAMERA_CONFIG_FILE_NAME)


def get_general():
    # TODO use a cache
    
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
            
            raise
    
    try:
        data = json.load(file)
        _set_default_general(data)
        
        return data
    
    except Exception as e:
        logging.error('could not read config file %(path)s: %(msg)s' % {
                'path': config_file_path, 'msg': unicode(e)})
        
        raise
        
    finally:
        file.close()
        

def set_general(data):
    # TODO use a cache
    
    _set_default_general(data)

    config_file_path = os.path.join(settings.PROJECT_PATH, _GENERAL_CONFIG_FILE_PATH)
    
    logging.info('writing general config to file %(path)s...' % {'path': config_file_path})
    
    try:
        file = open(config_file_path, 'w')
    
    except Exception as e:
        logging.error('could not open config file %(path)s for writing: %(msg)s' % {
                'path': config_file_path, 'msg': unicode(e)})
        
        raise
    
    try:
        json.dump(data, file)
    
    except Exception as e:
        logging.error('could not write config file %(path)s: %(msg)s' % {
                'path': config_file_path, 'msg': unicode(e)})
        
    finally:
        file.close()

    return data


def get_camera(camera_id):
    # TODO use a cache
    
    config_path = os.path.join(settings.PROJECT_PATH, _CONFIG_DIR)
    camera_config_path = os.path.join(config_path, _CAMERA_CONFIG_FILE_NAME % {'id': camera_id})
    
    logging.info('reading camera config from %(path)s...' % {'path': camera_config_path})
    
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
    
    return _conf_to_dict(lines)


def set_camera(camera_id, data):
    # TODO use a cache
    
    config_path = os.path.join(settings.PROJECT_PATH, _CONFIG_DIR)
    camera_config_path = os.path.join(config_path, _CAMERA_CONFIG_FILE_NAME % {'id': camera_id})
    
    # read the actual configuration from file
    
    logging.info('reading camera config from %(path)s...' % {'path': camera_config_path})
    
    try:
        file = open(camera_config_path, 'r')
    
    except Exception as e:
        logging.error('could not open camera config file %(path)s: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        raise
    
    try:
        lines = [l[:-1] for l in file.readlines()]
    
    except Exception as e:
        logging.error('could not read camera config file %(path)s: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        raise
    
    finally:
        file.close()
    
    # write the configuration to file
    
    logging.info('writing camera config to %(path)s...' % {'path': camera_config_path})
    
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
    
    cameras = get_general().get('cameras', {})
    camera_ids = [int(k) for k in cameras.iterkeys()]

    last_camera_id = max(camera_ids or [0])
    camera_id = last_camera_id + 1
    
    logging.info('adding new camera with id %(id)s...' % {'id': camera_id})
        
    # write the configuration to file
    
    config_path = os.path.join(settings.PROJECT_PATH, _CONFIG_DIR)
    camera_config_path = os.path.join(config_path, _CAMERA_CONFIG_FILE_NAME % {'id': camera_id})
    logging.info('writing camera config to %(path)s...' % {'path': camera_config_path})
    
    try:
        file = open(camera_config_path, 'w')
    
    except Exception as e:
        logging.error('could not open camera config file %(path)s for writing: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        raise
    
    # add the default camera config
    ui = camera_dict_to_ui(camera_id, {})
    data = camera_ui_to_dict(camera_id, ui)
    
    lines = _dict_to_conf([], data)
    
    try:
        file.writelines([l + '\n' for l in lines])
    
    except Exception as e:
        logging.error('could not write camera config file %(path)s: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        raise
    
    finally:
        file.close()
    
    # add the camera to the general config
    
    cameras[camera_id] = {
        'name': 'camera' + str(camera_id),
        'device': device,
        'enabled': True
    }
    
    general_config = get_general()
    general_config['cameras'] = cameras
    
    set_general(general_config)
    
    return camera_id, cameras[camera_id]['name'], data


def rem_camera(camera_id):
    # TODO use a cache
    
    # TODO remove the camera from general config as well
    
    config_path = os.path.join(settings.PROJECT_PATH, _CONFIG_DIR)
    camera_config_path = os.path.join(config_path, _CAMERA_CONFIG_FILE_NAME % {'id': camera_id})
    
    logging.info('removing camera config file %(path)s...' % {'path': camera_config_path})
    
    try:
        os.remove(camera_config_path)
    
    except Exception as e:
        logging.error('could not remove camera config file %(path)s: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        raise


def camera_ui_to_dict(camera_id, ui):
    cameras = get_general().get('cameras', {})
    camera_info = cameras.get(camera_id, {})
    camera_name = camera_info.get('name', '(unknown)')

    data = {
        # device
        'lightswitch': int(ui.get('light_switch_detect', False) * 5),
        'auto_brightness': ui.get('auto_brightness', False),
        'brightness': int(int(ui.get('brightness', 0)) * 2.55),
        'contrast': int(int(ui.get('contrast', 0)) * 2.55),
        'saturation': int(int(ui.get('saturation', 0)) * 2.55),
        'hue': int(int(ui.get('hue', 0))),
        'width': int(ui.get('resolution', '352x288').split('x')[0]),
        'height': int(ui.get('resolution', '352x288').split('x')[1]),
        'framerate': int(ui.get('framerate', 1)),
        
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
            data['text_left'] = camera_name
            
        elif left_text == 'timestamp':
            data['text_left'] = '%Y-%m-%d\n%T'
            
        else:
            data['text_left'] = ui.get('custom_left_text', '')
        
        right_text = ui.get('right_text', 'timestamp')
        if right_text == 'camera-name':
            data['text_right'] = camera_name
            
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
    # this is where the default values come from
    
    cameras = get_general().get('cameras', {})
    camera_info = cameras.get(camera_id, {})
    camera_name = camera_info.get('name', '(unknown)')
    
    ui = {
        # device
        'light_switch_detect': data.get('lightswitch', 0) > 0,
        'auto_brightness': data.get('auto_brightness', False),
        'brightness': int(int(data.get('brightness', 0)) / 2.55),
        'contrast': int(int(data.get('contrast', 0)) / 2.55),
        'saturation': int(int(data.get('saturation', 0)) / 2.55),
        'hue': int(int(data.get('hue', 0))),
        'resolution': str(data.get('width', 352)) + 'x' + str(data.get('height', 288)),
        'framerate': int(data.get('framerate', 1)),
        
        # text overlay
        'text_overlay': False,
        'left_text': 'camera-name',
        'right_text': 'timestamp',
        
        # streaming
        'vudeo_streaming': not data.get('webcam_localhost', False),
        'streaming_port': int(data.get('webcam_port', 8080)),
        'streaming_framerate': int(data.get('webcam_maxrate', 1)),
        'streaming_quality': int(data.get('webcam_quality', 50)),
        
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
        'frame_change_threshold': data.get('threshold', 1500),
        'auto_noise_detect': data.get('noise_tune', True),
        'noise_level': int(int(data.get('noise_level', 32)) / 2.55),
        'gap': int(data.get('gap', 60)),
        'pre_capture': int(data.get('pre_capture', 0)),
        'post_capture': int(data.get('post_capture', 0)),
        
        # TODO notifications
    }
    
    text_left = data.get('text_left', '')
    text_right = data.get('text_right', '') 
    if text_left or text_right:
        ui['text_overlay'] = True
        
        if text_left == camera_name:
            ui['left_text'] = 'camera-name'
            
        elif text_left == '%Y-%m-%d\n%T':
            ui['left_text'] = 'timestamp'
            
        else:
            ui['left_text'] = 'custom-text'
            ui['custom_left_text'] = text_left

        if text_right == camera_name:
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
    snapshot_filename = data.get('snapshpt_filename')
    
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
        ui['movie_quality'] = int((max(2, data.get('ffmpeg_variable_bitrate', 14)) - 2) / 0.29)
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
    data.setdefault('general_enabled', True)
    data.setdefault('show_advanced', False)
    data.setdefault('admin_username', 'admin')
    data.setdefault('admin_password', '')
    data.setdefault('normal_username', 'user')
    data.setdefault('storage_device', 'local-disk')
    data.setdefault('root_directory', '/')
    data.setdefault('cameras', {})


def _set_default_motion(data):
    pass # TODO

