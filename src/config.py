
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

from collections import OrderedDict

import settings
import utils
import v4l2ctl


_CAMERA_CONFIG_FILE_NAME = 'thread-%(id)s.conf'

_MAIN_CONFIG_FILE_PATH = os.path.join(settings.CONF_PATH, 'motion.conf')
_CAMERA_CONFIG_FILE_PATH = os.path.join(settings.CONF_PATH, _CAMERA_CONFIG_FILE_NAME)

_main_config_cache = None
_camera_config_cache = None
_camera_ids_cache = None


def get_main(as_lines=False):
    global _main_config_cache
    
    if not as_lines and _main_config_cache is not None:
        return _main_config_cache
    
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
    
    _main_config_cache = data
    
    return data


def set_main(data):
    global _main_config_cache
    
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

    _main_config_cache = data

    return data


def get_camera_ids():
    global _camera_ids_cache
    
    if _camera_ids_cache is not None:
        return _camera_ids_cache

    config_path = settings.CONF_PATH
    
    logging.debug('listing config dir %(path)s...' % {'path': config_path})
    
    try:
        ls = os.listdir(config_path)
    
    except Exception as e:
        logging.error('failed to list config dir %(path)s: %(msg)s', {
                'path': config_path, 'msg': unicode(e)})
        
        raise
    
    camera_ids = []
    
    pattern = '^' + _CAMERA_CONFIG_FILE_NAME.replace('%(id)s', '(\d+)') + '$'
    for name in ls:
        match = re.match(pattern, name)
        if match:
            camera_id = int(match.groups()[0])
            logging.debug('found camera with id %(id)s' % {
                    'id': camera_id})
            
            camera_ids.append(camera_id)
        
    camera_ids.sort()
    
    _camera_ids_cache = camera_ids
    
    return camera_ids


def has_enabled_cameras():
    if not get_main().get('@enabled'):
        return False
    
    camera_ids = get_camera_ids()
    cameras = [get_camera(camera_id) for camera_id in camera_ids]
    return bool([c for c in cameras if c['@enabled'] and c['@proto'] == 'v4l2'])


def get_camera(camera_id, as_lines=False):
    global _camera_config_cache
    
    if not as_lines and _camera_config_cache is not None and camera_id in _camera_config_cache:
        return _camera_config_cache[camera_id]
    
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
    
    data.setdefault('@proto', 'v4l2')
    
    # determine the enabled status
    if data['@proto'] == 'v4l2':
        main_config = get_main()
        threads = main_config.get('thread', [])
        data['@enabled'] = _CAMERA_CONFIG_FILE_NAME % {'id': camera_id} in threads
        data['@id'] = camera_id

        _set_default_motion_camera(data)
    
    if _camera_config_cache is None:
        _camera_config_cache = {}
    
    _camera_config_cache[camera_id] = data
    
    return data


def set_camera(camera_id, data):
    global _camera_config_cache
    
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
        
        data['@id'] = camera_id
        
        set_main(main_config)
        
        # try to create the target_dir
        try:
            os.makedirs(data['target_dir'])
        
        except OSError as e:
            if e.errno != errno.EEXIST:
                logging.warn('failed to create target directory: %(msg)s' % {'msg': unicode(e)})

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
        
    if _camera_config_cache is None:
        _camera_config_cache = {}
    
    _camera_config_cache[camera_id] = data
    
    return data


def add_camera(device_details):
    global _camera_ids_cache
    global _camera_config_cache
    
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
            data['ffmpeg_bps'] = device_details['ffmpeg_bps']
        
    else: # remote
        data['@host'] = device_details['host']
        data['@port'] = device_details['port']
        data['@username'] = device_details['username']
        data['@password'] = device_details['password']
        data['@remote_camera_id'] = device_details['remote_camera_id']
        data['@enabled'] = device_details.get('enabled', True)

    # write the configuration to file
    set_camera(camera_id, data)
    
    _camera_ids_cache = None
    _camera_config_cache = None
    
    return camera_id, data


def rem_camera(camera_id):
    global _camera_ids_cache
    global _camera_config_cache
    
    camera_config_name = _CAMERA_CONFIG_FILE_NAME % {'id': camera_id}
    camera_config_path = _CAMERA_CONFIG_FILE_PATH % {'id': camera_id}
    
    # remove the camera from the main config
    main_config = get_main()
    threads = main_config.setdefault('thread', [])
    threads = [t for t in threads if t != camera_config_name]
    
    main_config['thread'] = threads

    set_main(main_config)
    
    logging.info('removing camera config file %(path)s...' % {'path': camera_config_path})
    
    _camera_ids_cache = None
    _camera_config_cache = None
    
    try:
        os.remove(camera_config_path)
    
    except Exception as e:
        logging.error('could not remove camera config file %(path)s: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        raise


def main_ui_to_dict(ui):
    return {
        '@enabled': ui.get('enabled', True),
        '@show_advanced': ui.get('show_advanced', False),
        '@admin_username': ui.get('admin_username', ''),
        '@admin_password': ui.get('admin_password', ''),
        '@normal_username': ui.get('normal_username', ''),
        '@normal_password': ui.get('normal_password', '')
    }


def main_dict_to_ui(data):
    return {
        'enabled': data.get('@enabled', True),
        'show_advanced': data.get('@show_advanced', False),
        'admin_username': data.get('@admin_username', ''),
        'admin_password': data.get('@admin_password', ''),
        'normal_username': data.get('@normal_username', ''),
        'normal_password': data.get('@normal_password', '')
    }


def camera_ui_to_dict(ui):
    if not ui.get('resolution'):  # avoid errors for empty resolution setting
        ui['resolution'] = '352x288'

    data = {
        # device
        '@name': ui.get('name', ''),
        '@enabled': ui.get('enabled', False),
        '@proto': ui.get('proto', 'v4l2'),
        'videodevice': ui.get('device', ''),
        'lightswitch': int(ui.get('light_switch_detect', True)) * 5,
        'auto_brightness': ui.get('auto_brightness', False),
        'width': int(ui['resolution'].split('x')[0]),
        'height': int(ui['resolution'].split('x')[1]),
        'framerate': int(ui.get('framerate', 1)),
        'rotate': int(ui.get('rotation', 0)),
        
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
        'text_double': False,
        
        # streaming
        'webcam_localhost': not ui.get('video_streaming', True),
        'webcam_port': int(ui.get('streaming_port', 8080)),
        'webcam_maxrate': int(ui.get('streaming_framerate', 1)),
        'webcam_quality': max(1, int(ui.get('streaming_quality', 85))),
        'webcam_motion': ui.get('streaming_motion', False),
        
        # still images
        'output_normal': False,
        'output_all': False,
        'output_motion': False,
        'snapshot_interval': 0,
        'jpeg_filename': '',
        'snapshot_filename': '',
        '@preserve_pictures': int(ui.get('preserve_pictures', 0)),
        
        # movies
        'ffmpeg_cap_new': ui.get('motion_movies', False),
        'movie_filename': ui.get('movie_file_name', ''),
        '@preserve_movies': int(ui.get('preserve_movies', 0)),
    
        # motion detection
        'text_changes': ui.get('show_frame_changes', False),
        'locate': ui.get('show_frame_changes', False),
        'threshold': ui.get('frame_change_threshold', 1500),
        'noise_tune': ui.get('auto_noise_detect', True),
        'noise_level': max(1, int(round(int(ui.get('noise_level', 8)) * 2.55))),
        'gap': int(ui.get('gap', 60)),
        'pre_capture': int(ui.get('pre_capture', 0)),
        'post_capture': int(ui.get('post_capture', 0)),
        
        # motion notifications
        '@motion_notifications': ui.get('motion_notifications', False),
        '@motion_notifications_emails': ui.get('motion_notifications_emails', ''),
        
        # working schedule
        '@working_schedule': ''
    }
    
    if 'brightness' in ui:
        if int(ui['brightness']) == 50:
            data['brightness'] = 0
            
        else:
            data['brightness'] = max(1, int(round(int(ui['brightness']) * 2.55)))
    
    if 'contrast' in ui:
        if int(ui['contrast']) == 50:
            data['contrast'] = 0
            
        else:
            data['contrast'] = max(1, int(round(int(ui['contrast']) * 2.55)))
    
    if 'saturation' in ui:
        if int(ui['saturation']) == 50:
            data['saturation'] = 0
            
        else:
            data['saturation'] = max(1, int(round(int(ui['saturation']) * 2.55)))
        
    if 'hue' in ui:
        if int(ui['hue']) == 50:
            data['hue'] = 0
            
        else:
            data['hue'] = max(1, int(round(int(ui['hue']) * 2.55)))

    if ui.get('text_overlay', False):
        left_text = ui.get('left_text', 'camera-name')
        if left_text == 'camera-name':
            data['text_left'] = ui.get('name')
            
        elif left_text == 'timestamp':
            data['text_left'] = '%Y-%m-%d\\n%T'
            
        else:
            data['text_left'] = ui.get('custom_left_text', '')
        
        right_text = ui.get('right_text', 'timestamp')
        if right_text == 'camera-name':
            data['text_right'] = ui.get('name')
            
        elif right_text == 'timestamp':
            data['text_right'] = '%Y-%m-%d\\n%T'
            
        else:
            data['text_right'] = ui.get('custom_right_text', '')
        
        if data['width'] > 320:
            data['text_double'] = True
    
    if ui.get('still_images', False):
        capture_mode = ui.get('capture_mode', 'motion-triggered')
        if capture_mode == 'motion-triggered':
            data['output_normal'] = True
            data['jpeg_filename'] = ui.get('image_file_name', '')  
            
        elif capture_mode == 'interval-snapshots':
            data['snapshot_interval'] = int(ui.get('snapshot_interval', 300))
            data['snapshot_filename'] = ui.get('image_file_name', '')
            
        elif capture_mode == 'all-frames':
            data['output_all'] = True
            data['jpeg_filename'] = ui.get('image_file_name', '')
            
        data['quality'] = max(1, int(ui.get('image_quality', 85)))
    
    if ui.get('motion_movies'):
        max_val = data['width'] * data['height'] * data['framerate'] / 3
        max_val = min(max_val, 9999999)
        
        data['ffmpeg_bps'] = int(ui.get('movie_quality', 85)) * max_val / 100

    if ui.get('working_schedule', False):
        data['@working_schedule'] = (
                ui.get('monday_from', '') + '-' + ui.get('monday_to') + '|' + 
                ui.get('tuesday_from', '') + '-' + ui.get('tuesday_to') + '|' + 
                ui.get('wednesday_from', '') + '-' + ui.get('wednesday_to') + '|' + 
                ui.get('thursday_from', '') + '-' + ui.get('thursday_to') + '|' + 
                ui.get('friday_from', '') + '-' + ui.get('friday_to') + '|' + 
                ui.get('saturday_from', '') + '-' + ui.get('saturday_to') + '|' + 
                ui.get('sunday_from', '') + '-' + ui.get('sunday_to'))

    return data
    

def camera_dict_to_ui(data):
    if data['@proto'] == 'v4l2':
        device_uri = data['videodevice']
        usage = utils.get_disk_usage(data['target_dir'])
        if usage:
            disk_used, disk_total = usage
        
        else:
            disk_used, disk_total = 0, 0
    
    else:
        device_uri = '%(host)s:%(port)s/config/%(camera_id)s' % {
                'username': data['@username'],
                'password': '***',
                'host': data['@host'],
                'port': data['@port'],
                'camera_id': data['@remote_camera_id']}
        
        disk_used, disk_total = data['disk_used'], data['disk_total']
    
    ui = {
        # device
        'name': data['@name'],
        'enabled': data['@enabled'],
        'id': data.get('@id'),
        'proto': data['@proto'],
        'device': device_uri,
        'light_switch_detect': data.get('lightswitch') > 0,
        'auto_brightness': data.get('auto_brightness'),
        'resolution': str(data.get('width')) + 'x' + str(data.get('height')),
        'framerate': int(data.get('framerate')),
        'rotation': int(data.get('rotate')),
        
        # file storage
        'storage_device': data['@storage_device'],
        'network_server': data['@network_server'],
        'network_share_name': data['@network_share_name'],
        'network_username': data['@network_username'],
        'network_password': data['@network_password'],
        'root_directory': data.get('target_dir'),
        'disk_used': disk_used,
        'disk_total': disk_total,
        
        # text overlay
        'text_overlay': False,
        'left_text': 'camera-name',
        'right_text': 'timestamp',
        'custom_left_text': '',
        'custom_right_text': '',
        
        # streaming
        'video_streaming': not data.get('webcam_localhost'),
        'streaming_port': int(data.get('webcam_port')),
        'streaming_framerate': int(data.get('webcam_maxrate')),
        'streaming_quality': int(data.get('webcam_quality')),
        'streaming_motion': int(data.get('webcam_motion')),
        
        # still images
        'still_images': False,
        'capture_mode': 'motion-triggered',
        'image_file_name': '%Y-%m-%d/%H-%M-%S',
        'image_quality': 85,
        'snapshot_interval': 0,
        'preserve_pictures': data['@preserve_pictures'],
        
        # motion movies
        'motion_movies': data.get('ffmpeg_cap_new'),
        'movie_file_name': data.get('movie_filename'),
        'preserve_movies': data['@preserve_movies'],

        # motion detection
        'show_frame_changes': data.get('text_changes') or data.get('locate'),
        'frame_change_threshold': data.get('threshold'),
        'auto_noise_detect': data.get('noise_tune'),
        'noise_level': int(int(data.get('noise_level')) / 2.55),
        'gap': int(data.get('gap')),
        'pre_capture': int(data.get('pre_capture')),
        'post_capture': int(data.get('post_capture')),
        
        # motion notifications
        'motion_notifications': data['@motion_notifications'],
        'motion_notifications_emails': data['@motion_notifications_emails'],
        
        # working schedule
        'working_schedule': False,
        'monday_from': '09:00', 'monday_to': '17:00',
        'tuesday_from': '09:00', 'tuesday_to': '17:00',
        'wednesday_from': '09:00', 'wednesday_to': '17:00',
        'thursday_from': '09:00', 'thursday_to': '17:00',
        'friday_from': '09:00', 'friday_to': '17:00',
        'saturday_from': '09:00', 'saturday_to': '17:00',
        'sunday_from': '09:00', 'sunday_to': '17:00'
    }

    # the brightness & co. keys in the ui dictionary
    # indicate the presence of these controls
    # we must call v4l2ctl functions to determine the available controls    
    if ui['proto'] == 'v4l2':
        brightness = v4l2ctl.get_brightness(ui['device'])
        if brightness is not None: # has brightness control
            if data.get('brightness') != 0:
                ui['brightness'] = brightness
                    
            else:
                ui['brightness'] = 50
            
        contrast = v4l2ctl.get_contrast(ui['device'])
        if contrast is not None: # has contrast control
            if data.get('contrast') != 0:
                ui['contrast'] = contrast
            
            else:
                ui['contrast'] = 50
            
        saturation = v4l2ctl.get_saturation(ui['device'])
        if saturation is not None: # has saturation control
            if data.get('saturation') != 0:
                ui['saturation'] = saturation
            
            else:
                ui['saturation'] = 50
            
        hue = v4l2ctl.get_hue(ui['device'])
        if hue is not None: # has hue control
            if data.get('hue') != 0:
                ui['hue'] = hue
            
            else:
                ui['hue'] = 50
            
    else: # remote
        if 'brightness' in data:
            ui['brightness'] = data['brightness']

        if 'contrast' in data:
            ui['contrast'] = data['contrast']

        if 'saturation' in data:
            ui['saturation'] = data['saturation']

        if 'hue' in data:
            ui['hue'] = data['hue']

    text_left = data.get('text_left')
    text_right = data.get('text_right') 
    if text_left or text_right:
        ui['text_overlay'] = True
        
        if text_left == data['@name']:
            ui['left_text'] = 'camera-name'
            
        elif text_left == '%Y-%m-%d\\n%T':
            ui['left_text'] = 'timestamp'
            
        else:
            ui['left_text'] = 'custom-text'
            ui['custom_left_text'] = text_left

        if text_right == data['@name']:
            ui['right_text'] = 'camera-name'
            
        elif text_right == '%Y-%m-%d\\n%T':
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
            
        elif snapshot_interval:
            ui['capture_mode'] = 'interval-snapshots'
            ui['image_file_name'] = snapshot_filename
            ui['snapshot_interval'] = snapshot_interval
            
        elif output_normal:
            ui['capture_mode'] = 'motion-triggered'
            ui['image_file_name'] = jpeg_filename  
            
        ui['image_quality'] = ui.get('quality', 85)

    ffmpeg_bps = data.get('ffmpeg_bps')
    if ffmpeg_bps is not None: 
        max_val = data['width'] * data['height'] * data['framerate'] / 3
        max_val = min(max_val, 9999999)
        
        ui['movie_quality'] = min(100, int(round(ffmpeg_bps * 100.0 / max_val))) 
    
    working_schedule = data.get('@working_schedule')
    if working_schedule:
        days = working_schedule.split('|')
        ui['monday_from'], ui['monday_to'] = days[0].split('-')
        ui['tuesday_from'], ui['tuesday_to'] = days[1].split('-')
        ui['wednesday_from'], ui['wednesday_to'] = days[2].split('-')
        ui['thursday_from'], ui['thursday_to'] = days[3].split('-')
        ui['friday_from'], ui['friday_to'] = days[4].split('-')
        ui['saturday_from'], ui['saturday_to'] = days[5].split('-')
        ui['sunday_from'], ui['sunday_to'] = days[6].split('-')
        ui['working_schedule'] = True
    
    return ui


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
    data.setdefault('@name', 'My Camera')
    data.setdefault('@enabled', False)
    data.setdefault('@proto', 'v4l2')
    data.setdefault('videodevice', '/dev/video0')
    data.setdefault('lightswitch', 5)
    data.setdefault('auto_brightness', False)
    data.setdefault('brightness', 0)
    data.setdefault('contrast', 0)
    data.setdefault('saturation', 0)
    data.setdefault('hue', 0)
    data.setdefault('width', 352)
    data.setdefault('height', 288)
    data.setdefault('framerate', 2)
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
    data.setdefault('webcam_quality', 85)
    data.setdefault('webcam_motion', False)
    
    data.setdefault('text_left', data['@name'])
    data.setdefault('text_right', '%Y-%m-%d\\n%T')
    data.setdefault('text_double', False)

    data.setdefault('text_changes', False)
    data.setdefault('locate', False)
    data.setdefault('threshold', 1500)
    data.setdefault('noise_tune', True)
    data.setdefault('noise_level', 32)
    data.setdefault('minimum_motion_frames', 5)
    
    data.setdefault('gap', 30)
    data.setdefault('pre_capture', 2)
    data.setdefault('post_capture', 4)
    
    data.setdefault('output_all', False)
    data.setdefault('output_normal', False)
    data.setdefault('jpeg_filename', '')
    data.setdefault('snapshot_interval', 0)
    data.setdefault('snapshot_filename', '')
    data.setdefault('quality', 85)
    data.setdefault('@preserve_pictures', 0)
    
    data.setdefault('ffmpeg_variable_bitrate', 0)
    data.setdefault('ffmpeg_bps', 400000)
    data.setdefault('movie_filename', '%Y-%m-%d/%H-%M-%S')
    data.setdefault('ffmpeg_cap_new', False)
    data.setdefault('@preserve_movies', 0)
    
    data.setdefault('@motion_notifications', False)
    data.setdefault('@motion_notifications_emails', '')
    
    data.setdefault('@working_schedule', '')
