
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

import collections
import datetime
import errno
import glob
import logging
import math
import os.path
import re
import shlex
import subprocess
import urlparse
import uuid
import hashlib
import base64

from tornado.ioloop import IOLoop
from Crypto.Cipher import AES
from Crypto import Random

import diskctl
import motionctl
import powerctl
import settings
import tasks
import uploadservices
import utils
import v4l2ctl

_CAMERA_CONFIG_FILE_NAME = 'thread-%(id)s.conf'
_MAIN_CONFIG_FILE_NAME = 'motion.conf'
_ACTIONS = ['lock', 'unlock', 'light_on', 'light_off', 'alarm_on', 'alarm_off', 'up', 'right', 'down', 'left', 'zoom_in', 'zoom_out',
        'preset1', 'preset2', 'preset3', 'preset4', 'preset5', 'preset6', 'preset7', 'preset8', 'preset9']

_main_config_cache = None
_camera_config_cache = {}
_camera_ids_cache = None
_additional_section_funcs = []
_additional_config_funcs = []
_additional_structure_cache = {}
_monitor_command_cache = {}

# when using the following video codecs, the ffmpeg_variable_bitrate parameter appears to have an exponential effect
_EXPONENTIAL_QUALITY_CODECS = ['mpeg4', 'msmpeg4', 'swf', 'flv', 'mov', 'mkv']
_EXPONENTIAL_QUALITY_FACTOR = 100000 # voodoo
_EXPONENTIAL_DEF_QUALITY = 511 # about 75%
_MAX_FFMPEG_VARIABLE_BITRATE = 32767
_BS=16

_KNOWN_MOTION_OPTIONS = set([
    'auto_brightness',
    'brightness',
    'contrast',
    'despeckle_filter',
    'emulate_motion',
    'event_gap',
    'ffmpeg_bps',
    'ffmpeg_output_debug_movies',
    'ffmpeg_output_movies',
    'ffmpeg_variable_bitrate',
    'ffmpeg_video_codec',
    'framerate',
    'height',
    'hue',
    'lightswitch',
    'locate_motion_mode',
    'locate_motion_style',
    'mask_file',
    'max_movie_time',
    'minimum_motion_frames',
    'movie_filename',
    'netcam_keepalive',
    'netcam_tolerant_check',
    'netcam_url',
    'netcam_userpass',
    'noise_level',
    'noise_tune',
    'on_event_end',
    'on_event_start',
    'on_movie_end',
    'on_picture_save',
    'output_debug_pictures',
    'output_motion',
    'output_pictures',
    'picture_filename',
    'post_capture',
    'pre_capture',
    'quality',
    'rotate',
    'rtsp_uses_tcp',
    'saturation',
    'smart_mask_speed',
    'snapshot_filename',
    'snapshot_interval',
    'stream_authentication',
    'stream_auth_method',
    'stream_localhost',
    'stream_maxrate',
    'stream_motion',
    'stream_port',
    'stream_quality',
    'target_dir',
    'text_changes',
    'text_double',
    'text_left',
    'text_right',
    'threshold',
    'videodevice',
    'width',
])

pad = lambda s: s + (_BS - len(s) % _BS ) * chr(_BS - len(s) % _BS)
unpad = lambda s : s[:-ord(s[len(s)-1:])]


def additional_section(func):
    _additional_section_funcs.append(func)


def additional_config(func):
    _additional_config_funcs.append(func)


import wifictl  # @UnusedImport
import tzctl  # @UnusedImport


def get_main(as_lines=False):
    global _main_config_cache
    
    if not as_lines and _main_config_cache is not None:
        return _main_config_cache
    
    config_file_path = os.path.join(settings.CONF_PATH, _MAIN_CONFIG_FILE_NAME)
    
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
                    'path': config_file_path, 'msg': unicode(e)})
            
            raise
        
        finally:
            file.close()
    
    if as_lines:
        return lines
    
    main_config = _conf_to_dict(lines,
            list_names=['thread'],
            no_convert=['@admin_username', '@admin_password', '@normal_username', '@normal_password'])

    _get_additional_config(main_config)
    _set_default_motion(main_config, old_config_format=motionctl.has_old_config_format())
  
    _main_config_cache = main_config
    _main_config_cache['@admin_password'] = decode_password(main_config['@admin_password'].encode('utf-8'))
    _main_config_cache['@normal_password'] = decode_password(main_config['@normal_password'].encode('utf-8'))

    return main_config


def set_main(main_config):
    global _main_config_cache
    
    main_config = dict(main_config)
    for n, v in _main_config_cache.iteritems():
        main_config.setdefault(n, v)
    _main_config_cache = main_config
    
    main_config = dict(main_config)
    _set_additional_config(main_config)

    config_file_path = os.path.join(settings.CONF_PATH, _MAIN_CONFIG_FILE_NAME)
    
    # read the actual configuration from file
    lines = get_main(as_lines=True)
    
    # write the configuration to file
    logging.debug('writing main config to %(path)s...' % {'path': config_file_path})
    
    try:
        file = open(config_file_path, 'w')
    
    except Exception as e:
        logging.error('could not open main config file %(path)s for writing: %(msg)s' % {
                'path': config_file_path, 'msg': unicode(e)})
        
        raise
    
    lines = _dict_to_conf(lines, main_config, list_names=['thread'])
    
    try:
        file.writelines([utils.make_str(l) + '\n' for l in lines])
    
    except Exception as e:
        logging.error('could not write main config file %(path)s: %(msg)s' % {
                'path': config_file_path, 'msg': unicode(e)})
        
        raise
    
    finally:
        file.close()


def get_camera_ids(filter_valid=True):
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
    
    if not filter_valid:
        return camera_ids

    filtered_camera_ids = []
    for camera_id in camera_ids:
        if get_camera(camera_id):
            filtered_camera_ids.append(camera_id)
    
    _camera_ids_cache = filtered_camera_ids
    
    return filtered_camera_ids


def get_enabled_local_motion_cameras():
    if not get_main().get('@enabled'):
        return []
    
    camera_ids = get_camera_ids()
    cameras = [get_camera(camera_id) for camera_id in camera_ids]
    return [c for c in cameras if c.get('@enabled') and utils.is_local_motion_camera(c)]


def get_network_shares():
    if not get_main().get('@enabled'):
        return []

    camera_ids = get_camera_ids()
    cameras = [get_camera(camera_id) for camera_id in camera_ids]
    
    mounts = []
    for camera in cameras:
        if camera.get('@storage_device') != 'network-share':
            continue
        
        mounts.append({
            'server': camera['@network_server'],
            'share': camera['@network_share_name'],
            'username': camera['@network_username'],
            'password': camera['@network_password'],
        })
        
    return mounts


def get_camera(camera_id, as_lines=False):
    if not as_lines and camera_id in _camera_config_cache:
        return _camera_config_cache[camera_id]
    
    camera_config_path = os.path.join(settings.CONF_PATH, _CAMERA_CONFIG_FILE_NAME) % {'id': camera_id}
    
    logging.debug('reading camera config from %(path)s...' % {'path': camera_config_path})
    
    try:
        file = open(camera_config_path, 'r')
    
    except Exception as e:
        logging.error('could not open camera config file: %(msg)s' % {'msg': unicode(e)})
        
        raise
    
    try:
        lines = [l.strip() for l in file.readlines()]
    
    except Exception as e:
        logging.error('could not read camera config file %(path)s: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        raise
    
    finally:
        file.close()
    
    if as_lines:
        return lines
        
    camera_config = _conf_to_dict(lines,
            no_convert=['@name', '@network_share_name', '@network_server',
                        '@network_username', '@network_password', '@storage_device',
                        '@upload_server', '@upload_username', '@upload_password'])
    
    if utils.is_local_motion_camera(camera_config):
        # determine the enabled status
        main_config = get_main()
        threads = main_config.get('thread', [])
        camera_config['@enabled'] = _CAMERA_CONFIG_FILE_NAME % {'id': camera_id} in threads
        camera_config['@id'] = camera_id
        
        old_config_format = motionctl.has_old_config_format()
        
        # adapt directives from old configuration, if needed
        if old_config_format:
            logging.debug('using old motion config directives')
            
            if 'output_normal' in camera_config:
                camera_config['output_pictures'] = camera_config.pop('output_normal')
            if 'output_all' in camera_config:
                camera_config['emulate_motion'] = camera_config.pop('output_all')
            if 'ffmpeg_cap_new' in camera_config:
                camera_config['ffmpeg_output_movies'] = camera_config.pop('ffmpeg_cap_new')
            if 'ffmpeg_cap_motion' in camera_config:
                camera_config['ffmpeg_output_debug_movies'] = camera_config.pop('ffmpeg_cap_motion')
            if 'locate' in camera_config:
                camera_config['locate_motion_mode'] = camera_config.pop('locate')
            if 'jpeg_filename' in camera_config:
                camera_config['picture_filename'] = camera_config.pop('jpeg_filename')
            if 'max_mpeg_time' in camera_config:
                camera_config['max_movie_time'] = camera_config.pop('max_mpeg_time')
            if 'webcam_port' in camera_config:
                camera_config['stream_port'] = camera_config.pop('webcam_port')
            if 'webcam_quality' in camera_config:
                camera_config['stream_quality'] = camera_config.pop('webcam_quality')
            if 'webcam_motion' in camera_config:
                camera_config['stream_motion'] = camera_config.pop('webcam_motion')
            if 'webcam_maxrate' in camera_config:
                camera_config['stream_maxrate'] = camera_config.pop('webcam_maxrate')
            if 'webcam_localhost' in camera_config:
                camera_config['stream_localhost'] = camera_config.pop('webcam_localhost')
            if 'gap' in camera_config:
                camera_config['event_gap'] = camera_config.pop('gap')
            if 'netcam_http' in camera_config:
                camera_config['netcam_keepalive'] = camera_config.pop('netcam_http') in ['1.1', 'keepalive']
            if 'despeckle' in camera_config:
                camera_config['despeckle_filter'] = camera_config.pop('despeckle')

        _get_additional_config(camera_config, camera_id=camera_id)
        
        _set_default_motion_camera(camera_id, camera_config)
    
    elif utils.is_remote_camera(camera_config):
        camera_config['@password'] = decode_password(camera_config['@password'])
        pass
    
    elif utils.is_simple_mjpeg_camera(camera_config):
        _get_additional_config(camera_config, camera_id=camera_id)
        
        _set_default_simple_mjpeg_camera(camera_id, camera_config)
    
    else: # incomplete configuration
        logging.warn('camera config file at %s is incomplete, ignoring' % camera_config_path)
        
        return None
    
    _camera_config_cache[camera_id] = dict(camera_config)
    
    return camera_config


def set_camera(camera_id, camera_config):
    camera_config['@id'] = camera_id
    _camera_config_cache[camera_id] = camera_config

    camera_config = dict(camera_config)
    
    if utils.is_local_motion_camera(camera_config):
        old_config_format = motionctl.has_old_config_format()
        
        # adapt directives to old configuration, if needed
        if old_config_format:
            logging.debug('using old motion config directives')
            
            if 'output_pictures' in camera_config:
                camera_config['output_normal'] = camera_config.pop('output_pictures')
            if 'emulate_motion' in camera_config:
                camera_config['output_all'] = camera_config.pop('emulate_motion')
            if 'ffmpeg_output_movies' in camera_config:
                camera_config['ffmpeg_cap_new'] = camera_config.pop('ffmpeg_output_movies')
            if 'ffmpeg_output_debug_movies' in camera_config:
                camera_config['ffmpeg_cap_motion'] = camera_config.pop('ffmpeg_output_debug_movies')
            if 'locate_motion_mode' in camera_config:
                camera_config['locate'] = camera_config.pop('locate_motion_mode')
            if 'picture_filename' in camera_config:
                camera_config['jpeg_filename'] = camera_config.pop('picture_filename')
            if 'max_movie_time' in camera_config:
                camera_config['max_mpeg_time'] = camera_config.pop('max_movie_time')
            if 'stream_port' in camera_config:
                camera_config['webcam_port'] = camera_config.pop('stream_port')
            if 'stream_quality' in camera_config:
                camera_config['webcam_quality'] = camera_config.pop('stream_quality')
            if 'stream_motion' in camera_config:
                camera_config['webcam_motion'] = camera_config.pop('stream_motion')
            if 'stream_maxrate' in camera_config:
                camera_config['webcam_maxrate'] = camera_config.pop('stream_maxrate')
            if 'stream_localhost' in camera_config:
                camera_config['webcam_localhost'] = camera_config.pop('stream_localhost')
            if 'stream_auth_method' in camera_config:
                camera_config.pop('stream_auth_method')
            if 'stream_authentication' in camera_config:
                camera_config.pop('stream_authentication')
            if 'event_gap' in camera_config:
                camera_config['gap'] = camera_config.pop('event_gap')
            if 'netcam_keepalive' in camera_config:
                camera_config['netcam_http'] = '1.1' if camera_config.pop('netcam_keepalive') else '1.0'
            if 'despeckle_filter' in camera_config:
                camera_config['despeckle'] = camera_config.pop('despeckle_filter')
         
        # set the enabled status in main config
        main_config = get_main()
        threads = main_config.setdefault('thread', [])
        config_file_name = _CAMERA_CONFIG_FILE_NAME % {'id': camera_id}
        if camera_config['@enabled'] and config_file_name not in threads:
            threads.append(config_file_name)
                
        elif not camera_config['@enabled']:
            threads = [t for t in threads if t != config_file_name]

        main_config['thread'] = threads
        
        set_main(main_config)
        _set_additional_config(camera_config, camera_id=camera_id)

    elif utils.is_remote_camera(camera_config):
        #encrypt remote camera password
        camera_config['@password'] = encode_password(camera_config['@password'])
        pass
    
    elif utils.is_simple_mjpeg_camera(camera_config):
        _set_additional_config(camera_config, camera_id=camera_id)

    # read the actual configuration from file
    config_file_path = os.path.join(settings.CONF_PATH, _CAMERA_CONFIG_FILE_NAME) % {'id': camera_id}
    if os.path.isfile(config_file_path):
        lines = get_camera(camera_id, as_lines=True)
    
    else:
        lines = []
    
    # write the configuration to file
    camera_config_path = os.path.join(settings.CONF_PATH, _CAMERA_CONFIG_FILE_NAME) % {'id': camera_id}
    logging.debug('writing camera config to %(path)s...' % {'path': camera_config_path})
    
    try:
        file = open(camera_config_path, 'w')
    
    except Exception as e:
        logging.error('could not open camera config file %(path)s for writing: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        raise
    
    lines = _dict_to_conf(lines, camera_config)
    
    try:
        file.writelines([utils.make_str(l) + '\n' for l in lines])
    
    except Exception as e:
        logging.error('could not write camera config file %(path)s: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        raise
    
    finally:
        file.close()
        

def add_camera(device_details):
    global _camera_ids_cache
    
    proto = device_details['proto']
    if proto in ['netcam', 'mjpeg']:
        host = device_details['host']
        if device_details['port']:
            host += ':' + str(device_details['port'])

        if device_details['username'] and proto == 'mjpeg':
            if device_details['password']:
                host = device_details['username'] + ':' + device_details['password'] + '@' + host
                
            else:
                host = device_details['username'] + '@' + host

        device_details['url'] = urlparse.urlunparse((device_details['scheme'], host, device_details['path'], '', '', ''))

    # determine the last camera id
    camera_ids = get_camera_ids()

    camera_id = 1
    while camera_id in camera_ids:
        camera_id += 1
    
    logging.info('adding new camera with id %(id)s...' % {'id': camera_id})
    
    # prepare a default camera config
    camera_config = {'@enabled': True}
    if proto == 'v4l2':
        # find a suitable resolution
        for (w, h) in v4l2ctl.list_resolutions(device_details['path']):
            if w > 300:
                camera_config['width'] = w
                camera_config['height'] = h
                break

        camera_config['videodevice'] = device_details['path']
    
    elif proto == 'motioneye':
        camera_config['@proto'] = 'motioneye'
        camera_config['@scheme'] = device_details['scheme']
        camera_config['@host'] = device_details['host']
        camera_config['@port'] = device_details['port']
        camera_config['@path'] = device_details['path']
        camera_config['@username'] = device_details['username']
        camera_config['@password'] = device_details['password']
        camera_config['@remote_camera_id'] = device_details['remote_camera_id']

    elif proto == 'netcam':
        camera_config['netcam_url'] = device_details['url']
        camera_config['text_double'] = True
        
        if device_details['username']:
            camera_config['netcam_userpass'] = device_details['username'] + ':' + device_details['password']
        
        camera_config['netcam_keepalive'] = device_details.get('keep_alive', False)
        camera_config['netcam_tolerant_check'] = True

        if device_details.get('camera_index') == 'udp':
            camera_config['rtsp_uses_tcp'] = False
        
        if camera_config['netcam_url'].startswith('rtsp'):
            camera_config['width'] = 640
            camera_config['height'] = 480

    else: # assuming mjpeg
        camera_config['@proto'] = 'mjpeg'
        camera_config['@url'] = device_details['url']
    
    if utils.is_local_motion_camera(camera_config):
        _set_default_motion_camera(camera_id, camera_config)

        # go through the config conversion functions back and forth once
        camera_config = motion_camera_ui_to_dict(motion_camera_dict_to_ui(camera_config), camera_config)
    
    elif utils.is_simple_mjpeg_camera(camera_config):
        _set_default_simple_mjpeg_camera(camera_id, camera_config)

        # go through the config conversion functions back and forth once
        camera_config = simple_mjpeg_camera_ui_to_dict(simple_mjpeg_camera_dict_to_ui(camera_config), camera_config)

    # write the configuration to file
    set_camera(camera_id, camera_config)
    
    _camera_ids_cache = None
    _camera_config_cache.clear()
    
    camera_config = get_camera(camera_id)
    
    return camera_config


def rem_camera(camera_id):
    global _camera_ids_cache
    
    camera_config_name = _CAMERA_CONFIG_FILE_NAME % {'id': camera_id}
    camera_config_path = os.path.join(settings.CONF_PATH, _CAMERA_CONFIG_FILE_NAME) % {'id': camera_id}
    
    # remove the camera from the main config
    main_config = get_main()
    threads = main_config.setdefault('thread', [])
    threads = [t for t in threads if t != camera_config_name]
    
    main_config['thread'] = threads

    set_main(main_config)
    
    logging.info('removing camera config file %(path)s...' % {'path': camera_config_path})
    
    _camera_ids_cache = None
    _camera_config_cache.clear()
    
    try:
        os.remove(camera_config_path)
    
    except Exception as e:
        logging.error('could not remove camera config file %(path)s: %(msg)s' % {
                'path': camera_config_path, 'msg': unicode(e)})
        
        raise


def main_ui_to_dict(ui):
    data = {
        '@show_advanced': ui['show_advanced'],
        '@admin_username': ui['admin_username'],
        '@admin_password': ui['admin_password'],
        '@normal_username': ui['normal_username'],
        '@normal_password': ui['normal_password']
    }

    # additional configs
    for name, value in ui.iteritems():
        if not name.startswith('_'):
            continue

        data['@' + name] = value

    return data


def main_dict_to_ui(data):
    ui = {
        'show_advanced': data['@show_advanced'],
        'admin_username': data['@admin_username'],
        'admin_password': decode_password(data['@admin_password']),
        'normal_username': data['@normal_username'],
        'normal_password': decode_password(data['@normal_password'])
    }

    # additional configs
    for name, value in data.iteritems():
        if not name.startswith('@_'):
            continue
        
        ui[name[1:]] = value

    return ui


def motion_camera_ui_to_dict(ui, old_config=None):
    import meyectl
    import smbctl
    
    old_config = dict(old_config or {})
    main_config = get_main() # needed for surveillance password

    data = {
        # device
        '@name': ui['name'],
        '@enabled': ui['enabled'],
        'auto_brightness': ui['auto_brightness'],
        'framerate': int(ui['framerate']),
        'rotate': int(ui['rotation']),
        
        # file storage
        '@storage_device': ui['storage_device'],
        '@network_server': ui['network_server'],
        '@network_share_name': ui['network_share_name'],
        '@network_username': ui['network_username'],
        '@network_password': ui['network_password'],
        '@upload_enabled': ui['upload_enabled'],
        '@upload_movie': ui['upload_movie'],
        '@upload_picture': ui['upload_picture'],
        '@upload_service': ui['upload_service'],
        '@upload_server': ui['upload_server'],
        '@upload_port': ui['upload_port'],
        '@upload_method': ui['upload_method'],
        '@upload_location': ui['upload_location'],
        '@upload_subfolders': ui['upload_subfolders'],
        '@upload_username': ui['upload_username'],
        '@upload_password': ui['upload_password'],
        
        # text overlay
        'text_left': '',
        'text_right': '',
        'text_double': False,
        
        # streaming
        'stream_localhost': not ui['video_streaming'],
        'stream_port': int(ui['streaming_port']),
        'stream_maxrate': int(ui['streaming_framerate']),
        'stream_quality': max(1, int(ui['streaming_quality'])),
        '@webcam_resolution': max(1, int(ui['streaming_resolution'])),
        '@webcam_server_resize': ui['streaming_server_resize'],
        'stream_motion': ui['streaming_motion'],
        'stream_auth_method': {'disabled': 0, 'basic': 1, 'digest': 2}.get(ui['streaming_auth_mode'], 0),
        'stream_authentication': main_config['@normal_username'] + ':' + main_config['@normal_password'],

        # still images
        'output_pictures': False,
        'snapshot_interval': 0,
        'picture_filename': '',
        'snapshot_filename': '',
        'quality': max(1, int(ui['image_quality'])),
        '@preserve_pictures': int(ui['preserve_pictures']),
        
        # movies
        'ffmpeg_output_movies': False,
        'movie_filename': ui['movie_file_name'],
        'max_movie_time': ui['max_movie_length'],
        '@preserve_movies': int(ui['preserve_movies']),
    
        # motion detection
        '@motion_detection': ui['motion_detection'],
        'emulate_motion': False,
        'text_changes': ui['show_frame_changes'],
        'locate_motion_mode': ui['show_frame_changes'],
        'noise_tune': ui['auto_noise_detect'],
        'noise_level': max(1, int(round(int(ui['noise_level']) * 2.55))),
        'lightswitch': ui['light_switch_detect'],
        'event_gap': int(ui['event_gap']),
        'pre_capture': int(ui['pre_capture']),
        'post_capture': int(ui['post_capture']),
        'minimum_motion_frames': int(ui['minimum_motion_frames']),
        'smart_mask_speed': 0,
        'mask_file': '',
        'output_debug_pictures': ui['create_debug_media'],
        'ffmpeg_output_debug_movies': ui['create_debug_media'],
        
        # working schedule
        '@working_schedule': '',
    
        # events
        'on_event_start': '',
        'on_event_end': '',
        'on_movie_end': '',
        'on_picture_save': ''
    }
    
    if utils.is_v4l2_camera(old_config):
        proto = 'v4l2'
        
    else:
        proto = 'netcam'
    
    if proto == 'v4l2':
        # leave videodevice unchanged
        
        # resolution
        if not ui['resolution']:
            ui['resolution'] = '320x240'

        width = int(ui['resolution'].split('x')[0])
        height = int(ui['resolution'].split('x')[1])
        data['width'] = width
        data['height'] = height
        
        threshold = int(float(ui['frame_change_threshold']) * width * height / 100)

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
    
    else: # assuming netcam
        if data.get('netcam_url', old_config.get('netcam_url', '')).startswith('rtsp'):
            # motion uses the configured width and height for RTSP cameras
            width = int(ui['resolution'].split('x')[0])
            height = int(ui['resolution'].split('x')[1])
            data['width'] = width
            data['height'] = height
            
            threshold = int(float(ui['frame_change_threshold']) * width * height / 100)
        
        else: # width & height are not available for other netcams
            threshold = int(float(ui['frame_change_threshold']) * 640 * 480 / 100)

    data['threshold'] = threshold

    if (ui['storage_device'] == 'network-share') and settings.SMB_SHARES:
        mount_point = smbctl.make_mount_point(ui['network_server'], ui['network_share_name'], ui['network_username'])
        if ui['root_directory'].startswith('/'):
            ui['root_directory'] = ui['root_directory'][1:]
        data['target_dir'] = os.path.normpath(os.path.join(mount_point, ui['root_directory']))
        
    elif ui['storage_device'].startswith('local-disk'):
        target_dev = ui['storage_device'][10:].replace('-', '/')
        mounted_partitions = diskctl.list_mounted_partitions()
        partition = mounted_partitions[target_dev]
        mount_point = partition['mount_point']
        
        if ui['root_directory'].startswith('/'):
            ui['root_directory'] = ui['root_directory'][1:]
        data['target_dir'] = os.path.normpath(os.path.join(mount_point, ui['root_directory']))

    else:
        data['target_dir'] = ui['root_directory']

    # try to create the target dir
    try:
        os.makedirs(data['target_dir'])
        logging.debug('created root directory %s for camera %s' % (data['target_dir'], data['@name']))
    
    except Exception as e:
        if isinstance(e, OSError) and e.errno == errno.EEXIST:
            pass # already exists, things should be just fine
        
        else:
            logging.error('failed to create root directory "%s": %s' % (data['target_dir'], e), exc_info=True)

    if ui['upload_enabled'] and '@id' in old_config:
        upload_settings = {k[7:]: ui[k] for k in ui.iterkeys() if k.startswith('upload_')}

        tasks.add(0, uploadservices.update, tag='uploadservices.update(%s)' % ui['upload_service'],
                camera_id=old_config['@id'], service_name=ui['upload_service'], settings=upload_settings)

    if ui['text_overlay']:
        left_text = ui['left_text']
        if left_text == 'camera-name':
            data['text_left'] = ui['name']
            
        elif left_text == 'timestamp':
            data['text_left'] = '%Y-%m-%d\\n%T'
            
        elif left_text == 'disabled':
            data['text_left'] = ''
            
        else:
            data['text_left'] = ui['custom_left_text']
        
        right_text = ui['right_text']
        if right_text == 'camera-name':
            data['text_right'] = ui['name']
            
        elif right_text == 'timestamp':
            data['text_right'] = '%Y-%m-%d\\n%T'
            
        elif right_text == 'disabled':
            data['text_right'] = ''
            
        else:
            data['text_right'] = ui['custom_right_text']
        
        if proto == 'netcam' or data['width'] > 320:
            data['text_double'] = True
    
    if ui['still_images']:
        capture_mode = ui['capture_mode']
        if capture_mode == 'motion-triggered':
            data['output_pictures'] = True
            data['picture_filename'] = ui['image_file_name']  
            
        elif capture_mode == 'interval-snapshots':
            data['snapshot_interval'] = int(ui['snapshot_interval'])
            data['snapshot_filename'] = ui['image_file_name']
            
        elif capture_mode == 'all-frames':
            data['output_pictures'] = True
            data['emulate_motion'] = True
            data['picture_filename'] = ui['image_file_name']
            
    if ui['movies']:
        data['ffmpeg_output_movies'] = True
        recording_mode = ui['recording_mode']
        if recording_mode == 'motion-triggered':
            data['emulate_motion'] = False

        elif recording_mode == 'continuous':
            data['emulate_motion'] = True

    data['ffmpeg_video_codec'] = ui['movie_format']
    q = int(ui['movie_quality'])
    if motionctl.needs_ffvb_quirks():
        if data['ffmpeg_video_codec'] in _EXPONENTIAL_QUALITY_CODECS:
            vbr = max(1, _MAX_FFMPEG_VARIABLE_BITRATE * (1 - math.log(max(1, q * _EXPONENTIAL_QUALITY_FACTOR), _EXPONENTIAL_QUALITY_FACTOR * 100)))
            
        else:
            vbr = 1 + (_MAX_FFMPEG_VARIABLE_BITRATE - 1) / 100.0 * (100 - q)
            
    else:
        vbr = max(1, q)

    data['ffmpeg_variable_bitrate'] = int(vbr)

    # motion detection

    if ui['despeckle_filter']:
        data['despeckle_filter'] = old_config['despeckle_filter'] or 'EedDl'

    else:
        data['despeckle_filter'] = ''

    if ui['mask']:
        if ui['mask_type'] == 'smart':
            data['smart_mask_speed'] = 10 - int(ui['smart_mask_sluggishness'])

        elif ui['mask_type'] == 'editable':
            capture_width, capture_height = data.get('width'), data.get('height')
            if data.get('rotate') in [90, 270]:
                capture_width, capture_height = capture_height, capture_width

            data['mask_file'] = utils.build_editable_mask_file(old_config['@id'], ui['mask_lines'], capture_width, capture_height)

    # working schedule
    if ui['working_schedule']:
        data['@working_schedule'] = (
                ui['monday_from'] + '-' + ui['monday_to'] + '|' + 
                ui['tuesday_from'] + '-' + ui['tuesday_to'] + '|' + 
                ui['wednesday_from'] + '-' + ui['wednesday_to'] + '|' + 
                ui['thursday_from'] + '-' + ui['thursday_to'] + '|' + 
                ui['friday_from'] + '-' + ui['friday_to'] + '|' + 
                ui['saturday_from'] + '-' + ui['saturday_to'] + '|' + 
                ui['sunday_from'] + '-' + ui['sunday_to'])
        
        data['@working_schedule_type'] = ui['working_schedule_type']
    
    # event start
    on_event_start = ['%(script)s start %%t' % {'script': meyectl.find_command('relayevent')}]
    if ui['email_notifications_enabled']:
        emails = re.sub('\\s', '', ui['email_notifications_addresses'])
        
        on_event_start.append("%(script)s '%(server)s' '%(port)s' '%(account)s' '%(password)s' '%(tls)s' '%(from)s' '%(to)s' 'motion_start' '%%t' '%%Y-%%m-%%dT%%H:%%M:%%S' '%(timespan)s'" % {
                'script': meyectl.find_command('sendmail'),
                'server': ui['email_notifications_smtp_server'],
                'port': ui['email_notifications_smtp_port'],
                'account': ui['email_notifications_smtp_account'],
                'password': ui['email_notifications_smtp_password'].replace(';', '\\;').replace('%', '%%'),
                'tls': ui['email_notifications_smtp_tls'],
                'from': ui['email_notifications_from'],
                'to': emails,
                'timespan': ui['email_notifications_picture_time_span']})

    if ui['web_hook_notifications_enabled']:
        url = re.sub('\\s', '+', ui['web_hook_notifications_url'])

        on_event_start.append("%(script)s '%(method)s' '%(url)s'" % {
                'script': meyectl.find_command('webhook'),
                'method': ui['web_hook_notifications_http_method'],
                'url': url})

    if ui['command_notifications_enabled']:
        on_event_start += utils.split_semicolon(ui['command_notifications_exec'])

    data['on_event_start'] = '; '.join(on_event_start)

    # event end
    on_event_end = ['%(script)s stop %%t' % {'script': meyectl.find_command('relayevent')}]
    
    data['on_event_end'] = '; '.join(on_event_end)
    
    # movie end
    on_movie_end = ['%(script)s movie_end %%t %%f' % {'script': meyectl.find_command('relayevent')}]
    
    if ui['web_hook_storage_enabled']:
        url = re.sub('\\s', '+', ui['web_hook_storage_url'])

        on_movie_end.append("%(script)s '%(method)s' '%(url)s'" % {
                'script': meyectl.find_command('webhook'),
                'method': ui['web_hook_storage_http_method'],
                'url': url})

    if ui['command_storage_enabled']:
        on_movie_end += utils.split_semicolon(ui['command_storage_exec'])

    data['on_movie_end'] = '; '.join(on_movie_end)
    
    # picture save
    on_picture_save = ['%(script)s picture_save %%t %%f' % {'script': meyectl.find_command('relayevent')}]
    
    if ui['web_hook_storage_enabled']:
        url = re.sub('\\s', '+', ui['web_hook_storage_url'])

        on_picture_save.append("%(script)s '%(method)s' '%(url)s'" % {
                'script': meyectl.find_command('webhook'),
                'method': ui['web_hook_storage_http_method'],
                'url': url})

    if ui['command_storage_enabled']:
        on_picture_save += utils.split_semicolon(ui['command_storage_exec'])

    data['on_picture_save'] = '; '.join(on_picture_save)

    # additional configs
    for name, value in ui.iteritems():
        if not name.startswith('_'):
            continue

        data['@' + name] = value
        
    # extra motion options
    for name in old_config.keys():
        if name not in _KNOWN_MOTION_OPTIONS and not name.startswith('@'):
            old_config.pop(name)

    extra_options = ui.get('extra_options', [])
    for name, value in extra_options:
        data[name] = value or ''

    old_config.update(data)

    return old_config


def motion_camera_dict_to_ui(data):
    import smbctl
    
    ui = {
        # device
        'name': data['@name'],
        'enabled': data['@enabled'],
        'id': data['@id'],
        'auto_brightness': data['auto_brightness'],
        'framerate': int(data['framerate']),
        'rotation': int(data['rotate']),
        
        # file storage
        'smb_shares': settings.SMB_SHARES,
        'storage_device': data['@storage_device'],
        'network_server': data['@network_server'],
        'network_share_name': data['@network_share_name'],
        'network_username': data['@network_username'],
        'network_password': data['@network_password'],
        'disk_used': 0,
        'disk_total': 0,
        'available_disks': diskctl.list_mounted_disks(),
        'upload_enabled': data['@upload_enabled'],
        'upload_picture': data['@upload_picture'],
        'upload_movie': data['@upload_movie'],
        'upload_service': data['@upload_service'],
        'upload_server': data['@upload_server'],
        'upload_port': data['@upload_port'],
        'upload_method': data['@upload_method'],
        'upload_location': data['@upload_location'],
        'upload_subfolders': data['@upload_subfolders'],
        'upload_username': data['@upload_username'],
        'upload_password': data['@upload_password'],
        'upload_authorization_key': '', # needed, otherwise the field is hidden
        'web_hook_storage_enabled': False,
        'command_storage_enabled': False,

        # text overlay
        'text_overlay': False,
        'left_text': 'camera-name',
        'right_text': 'timestamp',
        'custom_left_text': '',
        'custom_right_text': '',
        
        # streaming
        'video_streaming': not data['stream_localhost'],
        'streaming_framerate': int(data['stream_maxrate']),
        'streaming_quality': int(data['stream_quality']),
        'streaming_resolution': int(data['@webcam_resolution']),
        'streaming_server_resize': data['@webcam_server_resize'],
        'streaming_port': int(data['stream_port']),
        'streaming_auth_mode': {0: 'disabled', 1: 'basic', 2: 'digest'}.get(data.get('stream_auth_method'), 'disabled'),
        'streaming_motion': int(data['stream_motion']),
        
        # still images
        'still_images': False,
        'capture_mode': 'motion-triggered',
        'image_file_name': '%Y-%m-%d/%H-%M-%S',
        'image_quality': data['quality'],
        'snapshot_interval': 0,
        'preserve_pictures': data['@preserve_pictures'],
        
        # movies
        'movies': False,
        'recording_mode': 'motion-triggered',
        'movie_file_name': data['movie_filename'],
        'max_movie_length': data['max_movie_time'],
        'preserve_movies': data['@preserve_movies'],

        # motion detection
        'motion_detection': data['@motion_detection'],
        'show_frame_changes': data['text_changes'] or data['locate_motion_mode'],
        'auto_noise_detect': data['noise_tune'],
        'noise_level': int(int(data['noise_level']) / 2.55),
        'light_switch_detect': data['lightswitch'],
        'despeckle_filter': data['despeckle_filter'],
        'event_gap': int(data['event_gap']),
        'pre_capture': int(data['pre_capture']),
        'post_capture': int(data['post_capture']),
        'minimum_motion_frames': int(data['minimum_motion_frames']),
        'mask': False,
        'mask_type': 'smart',
        'smart_mask_sluggishness': 5,
        'mask_lines': [],
        'create_debug_media': data['ffmpeg_output_debug_movies'] or data['output_debug_pictures'],
        
        # motion notifications
        'email_notifications_enabled': False,
        'web_hook_notifications_enabled': False,
        'command_notifications_enabled': False,
        
        # working schedule
        'working_schedule': False,
        'working_schedule_type': 'during',
        'monday_from': '', 'monday_to': '',
        'tuesday_from': '', 'tuesday_to': '',
        'wednesday_from': '', 'wednesday_to': '',
        'thursday_from': '', 'thursday_to': '',
        'friday_from': '', 'friday_to': '',
        'saturday_from': '', 'saturday_to': '',
        'sunday_from': '', 'sunday_to': ''
    }
    
    if utils.is_net_camera(data):
        ui['device_url'] = data['netcam_url']
        ui['proto'] = 'netcam'

        # resolutions
        if data['netcam_url'].startswith('rtsp'):
            # motion uses the configured width and height for RTSP cameras
            resolutions = utils.COMMON_RESOLUTIONS
            resolutions = [r for r in resolutions if motionctl.resolution_is_valid(*r)]
            ui['available_resolutions'] = [(str(w) + 'x' + str(h)) for (w, h) in resolutions]
            ui['resolution'] = str(data['width']) + 'x' + str(data['height'])

            threshold = data['threshold'] * 100.0 / (data['width'] * data['height'])

        else: # width & height are not available for other netcams
            # we have no other choice but use something like 640x480 as reference
            threshold = data['threshold'] * 100.0 / (640 * 480)

    else: # assuming v4l2
        ui['device_url'] = data['videodevice']
        ui['proto'] = 'v4l2'

        # resolutions
        resolutions = v4l2ctl.list_resolutions(data['videodevice'])
        ui['available_resolutions'] = [(str(w) + 'x' + str(h)) for (w, h) in resolutions]
        ui['resolution'] = str(data['width']) + 'x' + str(data['height'])
    
        # the brightness & co. keys in the ui dictionary
        # indicate the presence of these controls
        # we must call v4l2ctl functions to determine the available controls    
        brightness = v4l2ctl.get_brightness(data['videodevice'])
        if brightness is not None: # has brightness control
            if data.get('brightness', 0) != 0:
                ui['brightness'] = brightness
                    
            else:
                ui['brightness'] = 50

        contrast = v4l2ctl.get_contrast(data['videodevice'])
        if contrast is not None: # has contrast control
            if data.get('contrast', 0) != 0:
                ui['contrast'] = contrast
            
            else:
                ui['contrast'] = 50
            
        saturation = v4l2ctl.get_saturation(data['videodevice'])
        if saturation is not None: # has saturation control
            if data.get('saturation', 0) != 0:
                ui['saturation'] = saturation
            
            else:
                ui['saturation'] = 50
            
        hue = v4l2ctl.get_hue(data['videodevice'])
        if hue is not None: # has hue control
            if data.get('hue', 0) != 0:
                ui['hue'] = hue
            
            else:
                ui['hue'] = 50
        
        threshold = data['threshold'] * 100.0 / (data['width'] * data['height'])
        
    ui['frame_change_threshold'] = threshold
    
    if (data['@storage_device'] == 'network-share') and settings.SMB_SHARES:
        mount_point = smbctl.make_mount_point(data['@network_server'], data['@network_share_name'], data['@network_username'])
        ui['root_directory'] = data['target_dir'][len(mount_point):] or '/'
    
    elif data['@storage_device'].startswith('local-disk'):
        target_dev = data['@storage_device'][10:].replace('-', '/')
        mounted_partitions = diskctl.list_mounted_partitions()
        for partition in mounted_partitions.values():
            if partition['target'] == target_dev and data['target_dir'].startswith(partition['mount_point']):
                ui['root_directory'] = data['target_dir'][len(partition['mount_point']):] or '/'
                break

        else: # not found for some reason
            logging.error('could not find mounted partition for device "%s" and target dir "%s"' % (target_dev, data['target_dir']))
            ui['root_directory'] = data['target_dir']

    else:
        ui['root_directory'] = data['target_dir']

    # disk usage
    usage = None
    if os.path.exists(data['target_dir']):
        usage = utils.get_disk_usage(data['target_dir'])
    if usage:
        ui['disk_used'], ui['disk_total'] = usage

    text_left = data['text_left']
    text_right = data['text_right'] 
    if text_left or text_right:
        ui['text_overlay'] = True
        
        if text_left == data['@name']:
            ui['left_text'] = 'camera-name'
            
        elif text_left == '%Y-%m-%d\\n%T':
            ui['left_text'] = 'timestamp'

        elif text_left == '':
            ui['left_text'] = 'disabled'
            
        else:
            ui['left_text'] = 'custom-text'
            ui['custom_left_text'] = text_left

        if text_right == data['@name']:
            ui['right_text'] = 'camera-name'
            
        elif text_right == '%Y-%m-%d\\n%T':
            ui['right_text'] = 'timestamp'
            
        elif text_right == '':
            ui['right_text'] = 'disabled'

        else:
            ui['right_text'] = 'custom-text'
            ui['custom_right_text'] = text_right

    emulate_motion = data['emulate_motion']
    output_pictures = data['output_pictures']
    picture_filename = data['picture_filename']
    snapshot_interval = data['snapshot_interval']
    snapshot_filename = data['snapshot_filename']
    
    ui['still_images'] = (((emulate_motion or output_pictures) and picture_filename) or
            (snapshot_interval and snapshot_filename))
        
    if emulate_motion:
        ui['capture_mode'] = 'all-frames'
        if picture_filename:
            ui['image_file_name'] = picture_filename

    elif snapshot_interval:
        ui['capture_mode'] = 'interval-snapshots'
        ui['snapshot_interval'] = snapshot_interval
        if snapshot_filename:
            ui['image_file_name'] = snapshot_filename
        
    elif output_pictures:
        ui['capture_mode'] = 'motion-triggered'
        if picture_filename:
            ui['image_file_name'] = picture_filename

    if data['ffmpeg_output_movies']:
        ui['movies'] = True
        
    if emulate_motion:
        ui['recording_mode'] = 'continuous'  

    else:
        ui['recording_mode'] = 'motion-triggered'
        
    ui['movie_format'] = data['ffmpeg_video_codec']
    
    bitrate = data['ffmpeg_variable_bitrate']
    if motionctl.needs_ffvb_quirks():
        if data['ffmpeg_video_codec'] in _EXPONENTIAL_QUALITY_CODECS:
            q = (100 * _EXPONENTIAL_QUALITY_FACTOR) ** ((1 - float(bitrate) / _MAX_FFMPEG_VARIABLE_BITRATE)) / _EXPONENTIAL_QUALITY_FACTOR
    
        else:
            q = 100 - (bitrate - 1) * 100.0 / (_MAX_FFMPEG_VARIABLE_BITRATE - 1)
    
        ui['movie_quality'] = int(q)
        
    else:
        ui['movie_quality'] = bitrate

    # mask
    if data['mask_file']:
        ui['mask'] = True
        ui['mask_type'] = 'editable'
        
        capture_width, capture_height = data.get('width'), data.get('height')
        if int(data.get('rotate')) in [90, 270]:
            capture_width, capture_height = capture_height, capture_width
        
        ui['mask_lines'] = utils.parse_editable_mask_file(data['@id'], capture_width, capture_height)

    elif data['smart_mask_speed']:
        ui['mask'] = True
        ui['mask_type'] = 'smart'
        ui['smart_mask_sluggishness'] = 10 - data['smart_mask_speed']

    # working schedule
    working_schedule = data['@working_schedule']
    if working_schedule:
        days = working_schedule.split('|')
        ui['working_schedule'] = True
        ui['monday_from'], ui['monday_to'] = days[0].split('-')
        ui['tuesday_from'], ui['tuesday_to'] = days[1].split('-')
        ui['wednesday_from'], ui['wednesday_to'] = days[2].split('-')
        ui['thursday_from'], ui['thursday_to'] = days[3].split('-')
        ui['friday_from'], ui['friday_to'] = days[4].split('-')
        ui['saturday_from'], ui['saturday_to'] = days[5].split('-')
        ui['sunday_from'], ui['sunday_to'] = days[6].split('-')
        ui['working_schedule_type'] = data['@working_schedule_type']
    
    # event start
    on_event_start = data.get('on_event_start') or []
    if on_event_start:
        on_event_start = utils.split_semicolon(on_event_start)

    ui['email_notifications_picture_time_span'] = 0
    command_notifications = []
    for e in on_event_start:
        if e.count('sendmail'):
            e = shlex.split(e)

            if len(e) < 10:
                continue

            if len(e) < 16:
                # backwards compatibility with older configs lacking "from" field
                e.insert(-5, '')

            ui['email_notifications_enabled'] = True 
            ui['email_notifications_smtp_server'] = e[-11]
            ui['email_notifications_smtp_port'] = e[-10]
            ui['email_notifications_smtp_account'] = e[-9]
            ui['email_notifications_smtp_password'] = e[-8].replace('\\;', ';').replace('%%', '%')
            ui['email_notifications_smtp_tls'] = e[-7].lower() == 'true'
            ui['email_notifications_from'] = e[-6]
            ui['email_notifications_addresses'] = e[-5]
            try:
                ui['email_notifications_picture_time_span'] = int(e[-1])

            except:
                ui['email_notifications_picture_time_span'] = 0

        elif e.count('webhook'):
            e = shlex.split(e)

            if len(e) < 3:
                continue

            ui['web_hook_notifications_enabled'] = True 
            ui['web_hook_notifications_http_method'] = e[-2]
            ui['web_hook_notifications_url'] = e[-1]
        
        elif e.count('relayevent'):
            continue # ignore internal relay script

        else: # custom command
            command_notifications.append(e)
    
    if command_notifications: 
        ui['command_notifications_enabled'] = True
        ui['command_notifications_exec'] = '; '.join(command_notifications)

    # movie end
    on_movie_end = data.get('on_movie_end') or []
    if on_movie_end:
        on_movie_end = utils.split_semicolon(on_movie_end)

    command_storage = []
    for e in on_movie_end:
        if e.count('webhook'):
            e = shlex.split(e)

            if len(e) < 3:
                continue

            ui['web_hook_storage_enabled'] = True 
            ui['web_hook_storage_http_method'] = e[-2]
            ui['web_hook_storage_url'] = e[-1]

        elif e.count('relayevent'):
            continue # ignore internal relay script

        else: # custom command
            command_storage.append(e)
    
    if command_storage: 
        ui['command_storage_enabled'] = True
        ui['command_storage_exec'] = '; '.join(command_storage)

    # additional configs
    for name, value in data.iteritems():
        if not name.startswith('@_'):
            continue
        
        ui[name[1:]] = value
    
    # extra motion options
    extra_options = []
    for name, value in data.iteritems():
        if name not in _KNOWN_MOTION_OPTIONS and not name.startswith('@'):
            if isinstance(value, bool):
                value = ['off', 'on'][value] # boolean values should be transferred as on/off

            extra_options.append((name, value))

    ui['extra_options'] = extra_options
    
    # action commands
    action_commands = get_action_commands(data['@id'])
    ui['actions'] = action_commands.keys()

    return ui


def simple_mjpeg_camera_ui_to_dict(ui, old_config=None):
    old_config = dict(old_config or {})

    data = {
        # device
        '@name': ui['name'],
        '@enabled': ui['enabled'],
    }
    
    # additional configs
    for name, value in ui.iteritems():
        if not name.startswith('_'):
            continue

        data['@' + name] = value
        
    old_config.update(data)

    return old_config


def simple_mjpeg_camera_dict_to_ui(data):
    ui = {
        'name': data['@name'],
        'enabled': data['@enabled'],
        'id': data['@id'],
        'proto': 'mjpeg',
        'url': data['@url']
    }
    
    # additional configs
    for name, value in data.iteritems():
        if not name.startswith('@_'):
            continue
        
        ui[name[1:]] = value
    
    # action commands
    action_commands = get_action_commands(data['@id'])
    ui['actions'] = action_commands.keys()

    return ui


def get_action_commands(camera_id):
    action_commands = {}
    for action in _ACTIONS:
        path = os.path.join(settings.CONF_PATH, '%s_%s' % (action, camera_id))
        if os.access(path, os.X_OK):
            action_commands[action] = path
    
    return action_commands


def get_monitor_command(camera_id):
    if camera_id not in _monitor_command_cache:
        path = os.path.join(settings.CONF_PATH, 'monitor_%s' % camera_id)
        if os.access(path, os.X_OK):
            _monitor_command_cache[camera_id] = path
        
        else:
            _monitor_command_cache[camera_id] = None

    return _monitor_command_cache[camera_id]


def invalidate_monitor_commands():
    _monitor_command_cache.clear()


def backup():
    logging.debug('generating config backup file')

    if len(os.listdir(settings.CONF_PATH)) > 100:
        logging.debug('config path "%s" appears to be a system-wide config directory, performing a selective backup' % settings.CONF_PATH)
        cmd = ['tar', 'zc', 'motion.conf']
        cmd += map(os.path.basename, glob.glob(os.path.join(settings.CONF_PATH, 'thread-*.conf')))
        try:
            content = subprocess.check_output(cmd, cwd=settings.CONF_PATH)
            logging.debug('backup file created (%s bytes)' % len(content))
            
            return content
            
        except Exception as e:
            logging.error('backup failed: %s' % e, exc_info=True)
            
            return None

    else:
        logging.debug('config path "%s" appears to be a motion-specific config directory, performing a full backup' % settings.CONF_PATH)

        try:
            content = subprocess.check_output(['tar', 'zc', '.'], cwd=settings.CONF_PATH)
            logging.debug('backup file created (%s bytes)' % len(content))
            
            return content
            
        except Exception as e:
            logging.error('backup failed: %s' % e, exc_info=True)
            
            return None


def restore(content):
    global _main_config_cache
    global _camera_config_cache
    global _camera_ids_cache
    global _additional_structure_cache
    
    logging.info('restoring config from backup file')

    cmd = ['tar', 'zxC', settings.CONF_PATH]

    try:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        msg = p.communicate(content)[0]
        if msg:
            logging.error('failed to restore configuration: %s' % msg)
            return False

        logging.debug('configuration restored successfully')

        if settings.ENABLE_REBOOT:
            def later():
                powerctl.reboot()

            io_loop = IOLoop.instance()
            io_loop.add_timeout(datetime.timedelta(seconds=2), later)

        else:
            invalidate()

        return {'reboot': settings.ENABLE_REBOOT}

    except Exception as e:
        logging.error('failed to restore configuration: %s' % e, exc_info=True)

        return None


def invalidate():
    global _main_config_cache
    global _camera_config_cache
    global _camera_ids_cache
    global _additional_structure_cache

    logging.debug('invalidating config cache')    
    _main_config_cache = None
    _camera_config_cache = {}
    _camera_ids_cache = None
    _additional_structure_cache = {}


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


def _conf_to_dict(lines, list_names=[], no_convert=[]):
    data = utils.OrderedDict()
    
    for line in lines:
        line = line.strip()
        if len(line) == 0:  # empty line
            continue
        
        match = re.match('^\#\s*(\@\w+)\s*(.*)', line)
        if match:
            name, value = match.groups()[:2]
        
        elif line.startswith('#') or line.startswith(';'): # comment line
            continue

        else:
            parts = line.split(None, 1)
            if len(parts) == 1: # empty value
                parts.append('')

            (name, value) = parts
            
            value = value.strip()

        if name not in no_convert:
            value = _value_to_python(value)
        
        if name in list_names:
            data.setdefault(name, []).append(value)
        
        else:
            data[name] = value

    return data


def _dict_to_conf(lines, data, list_names=[]):
    conf_lines = []
    remaining = utils.OrderedDict(data)
    processed = set()
    
    # parse existing lines and replace the values
    
    for line in lines:
        line = line.strip()
        if len(line) == 0:  # empty line
            conf_lines.append(line)
            continue

        match = re.match('^\#\s*(\@\w+)\s*(.*)', line)
        if match: # @line
            (name, value) = match.groups()[:2]
        
        elif line.startswith('#') or line.startswith(';'):  # simple comment line
            conf_lines.append(line)
            continue
        
        else:
            parts = line.split(None, 1)
            if len(parts) == 2:
                (name, value) = parts
            
            else:
                (name, value) = parts[0], ''
            
        if name in processed:
            continue # name already processed
        
        processed.add(name)
        
        if name in list_names:
            new_value = data.get(name)
            if new_value is not None:
                for v in new_value:
                    if v is None:
                        continue

                    line = name + ' ' + _python_to_value(v)
                    conf_lines.append(line)
            
            else:
                line = name + ' ' + value
                conf_lines.append(line)

        else:
            new_value = data.get(name)
            if new_value is not None:
                value = _python_to_value(new_value).encode('utf-8')

                if name == '@admin_password':
                    value = encode_password(value)
                    
                if(name == '@normal_password'):
                    value = encode_password(value)
                    
                line = name + ' ' + value
                conf_lines.append(line)

        remaining.pop(name, None)

    # add the remaining config values not covered by existing lines
    
    if len(remaining) and len(lines):
        conf_lines.append('') # add a blank line
    
    for (name, value) in remaining.iteritems():
        if name.startswith('@_'):
            continue # ignore additional configs
        
        if name in list_names:
            for v in value:
                if v is None:
                    continue

                line = name + ' ' + _python_to_value(v)
                conf_lines.append(line)

        else:
            line = name + ' ' + _python_to_value(value)
            conf_lines.append(line)
            
    # build the final config lines
    conf_lines.sort(key=lambda l: not l.startswith('@'))
    
    lines = []
    for i, line in enumerate(conf_lines):
        # squeeze successive blank lines
        if i > 0 and len(line.strip()) == 0 and len(conf_lines[i - 1].strip()) == 0:
            continue
        
        if line.startswith('@'):
            line = '# ' + line
        
        elif i > 0 and conf_lines[i - 1].startswith('@'):
            lines.append('') # add a blank line between @lines and the rest
        
        lines.append(line)
        
    return lines


def _set_default_motion(data, old_config_format):
    data.setdefault('@enabled', True)
    data.setdefault('@application_uuid', create_system_uuid())

    data.setdefault('@show_advanced', False)
    data.setdefault('@admin_username', 'admin')
    data.setdefault('@admin_password', '')
    data.setdefault('@normal_username', 'user')
    data.setdefault('@normal_password', '')
    
    data.setdefault('setup_mode', False)

    if old_config_format:
        data.setdefault('control_port', settings.MOTION_CONTROL_PORT)
        data.setdefault('control_html_output', True)
        data.setdefault('control_localhost', settings.MOTION_CONTROL_LOCALHOST)
    
    else:
        data.setdefault('webcontrol_port', settings.MOTION_CONTROL_PORT)
        data.setdefault('webcontrol_html_output', True)
        data.setdefault('webcontrol_localhost', settings.MOTION_CONTROL_LOCALHOST)


def _set_default_motion_camera(camera_id, data):
    data.setdefault('@name', 'Camera' + str(camera_id))
    data.setdefault('@id', camera_id)
    
    if not utils.is_net_camera(data):
        data.setdefault('videodevice', '/dev/video0')
        data.setdefault('brightness', 0)
        data.setdefault('contrast', 0)
        data.setdefault('saturation', 0)
        data.setdefault('hue', 0)
        data.setdefault('width', 352)
        data.setdefault('height', 288)

    data.setdefault('auto_brightness', False)
    data.setdefault('framerate', 2)
    data.setdefault('rotate', 0)
    
    data.setdefault('@storage_device', 'custom-path')
    data.setdefault('@network_server', '')
    data.setdefault('@network_share_name', '')
    data.setdefault('@network_username', '')
    data.setdefault('@network_password', '')
    data.setdefault('target_dir', os.path.join(settings.MEDIA_PATH, data['@name']))
    data.setdefault('@upload_enabled', False)
    data.setdefault('@upload_picture', True)
    data.setdefault('@upload_movie', True)
    data.setdefault('@upload_service', 'ftp')
    data.setdefault('@upload_server', '')
    data.setdefault('@upload_port', '')
    data.setdefault('@upload_method', 'POST')
    data.setdefault('@upload_location', '')
    data.setdefault('@upload_subfolders', True)
    data.setdefault('@upload_username', '')
    data.setdefault('@upload_password', '')

    data.setdefault('stream_localhost', False)
    data.setdefault('stream_port', 8080 + camera_id)
    data.setdefault('stream_maxrate', 5)
    data.setdefault('stream_quality', 85)
    data.setdefault('stream_motion', False)
    data.setdefault('stream_auth_method', 0)

    data.setdefault('@webcam_resolution', 100)
    data.setdefault('@webcam_server_resize', False)
    
    data.setdefault('text_left', data['@name'])
    data.setdefault('text_right', '%Y-%m-%d\\n%T')
    data.setdefault('text_double', False)

    data.setdefault('@motion_detection', True)
    data.setdefault('text_changes', False)
    data.setdefault('locate_motion_mode', False)
    data.setdefault('locate_motion_style', 'redbox')
    
    data.setdefault('threshold', 2000)
    data.setdefault('noise_tune', True)
    data.setdefault('noise_level', 32)
    data.setdefault('lightswitch', 0)
    data.setdefault('despeckle_filter', '')
    data.setdefault('minimum_motion_frames', 20)
    data.setdefault('smart_mask_speed', 0)
    data.setdefault('mask_file', '')
    data.setdefault('ffmpeg_output_debug_movies', False)
    data.setdefault('output_debug_pictures', False)
    
    data.setdefault('pre_capture', 1)
    data.setdefault('post_capture', 1)
    
    data.setdefault('output_pictures', False)
    data.setdefault('picture_filename', '')
    data.setdefault('emulate_motion', False)
    data.setdefault('event_gap', 30)
    
    data.setdefault('snapshot_interval', 0)
    data.setdefault('snapshot_filename', '')
    data.setdefault('quality', 85)
    data.setdefault('@preserve_pictures', 0)
    
    data.setdefault('movie_filename', '%Y-%m-%d/%H-%M-%S')
    data.setdefault('max_movie_time', 0)
    data.setdefault('ffmpeg_output_movies', False)
    if motionctl.has_new_movie_format_support():
        data.setdefault('ffmpeg_video_codec', 'mp4') # will use h264 codec
        if motionctl.needs_ffvb_quirks():
            data.setdefault('ffmpeg_variable_bitrate', _MAX_FFMPEG_VARIABLE_BITRATE / 4) # 75%
            
        else:
            data.setdefault('ffmpeg_variable_bitrate', 75) # 75%
        
    else:
        data.setdefault('ffmpeg_video_codec', 'msmpeg4')
        data.setdefault('ffmpeg_variable_bitrate', _EXPONENTIAL_DEF_QUALITY)

    data.setdefault('@preserve_movies', 0)
    
    data.setdefault('@working_schedule', '')
    data.setdefault('@working_schedule_type', 'outside')

    data.setdefault('on_event_start', '')
    data.setdefault('on_event_end', '')
    data.setdefault('on_movie_end', '')
    data.setdefault('on_picture_save', '')


def _set_default_simple_mjpeg_camera(camera_id, data):
    data.setdefault('@name', 'Camera' + str(camera_id))
    data.setdefault('@id', camera_id)

    
def get_additional_structure(camera, separators=False):
    if _additional_structure_cache.get((camera, separators)) is None:
        logging.debug('loading additional config structure for %s, %s separators' % (
                'camera' if camera else 'main',
                'with' if separators else 'without'))

        # gather sections
        sections = utils.OrderedDict()
        for func in _additional_section_funcs:
            result = func()
            if not result:
                continue
            
            if result.get('reboot') and not settings.ENABLE_REBOOT:
                continue
            
            if bool(result.get('camera')) != bool(camera):
                continue
            
            result['name'] = func.func_name
            sections[func.func_name] = result
            
            logging.debug('additional config section: %s' % result['name'])
    
        configs = utils.OrderedDict()
        for func in _additional_config_funcs:
            result = func()
            if not result:
                continue
            
            if result.get('reboot') and not settings.ENABLE_REBOOT:
                continue
            
            if bool(result.get('camera')) != bool(camera):
                continue

            if result['type'] == 'separator' and not separators:
                continue

            result['name'] = func.func_name
            configs[func.func_name] = result
    
            section = sections.setdefault(result.get('section'), {})
            section.setdefault('configs', []).append(result)
            
            logging.debug('additional config item: %s' % result['name'])

        _additional_structure_cache[(camera, separators)] = sections, configs

    return _additional_structure_cache[(camera, separators)]


def _get_additional_config(data, camera_id=None):
    args = [camera_id] if camera_id else []
    
    (sections, configs) = get_additional_structure(camera=bool(camera_id))
    get_funcs = set([c.get('get') for c in configs.itervalues() if c.get('get')])
    get_func_values = collections.OrderedDict((f, f(*args)) for f in get_funcs)

    for name, section in sections.iteritems():
        if not section.get('get'):
            continue

        if section.get('get_set_dict'):
            data['@_' + name] = get_func_values.get(section['get'], {}).get(name)
            
        else:
            data['@_' + name] = get_func_values.get(section['get'])  

    for name, config in configs.iteritems():
        if not config.get('get'):
            continue

        if config.get('get_set_dict'):
            data['@_' + name] = get_func_values.get(config['get'], {}).get(name)
            
        else:
            data['@_' + name] = get_func_values.get(config['get']) 


def _set_additional_config(data, camera_id=None):
    args = [camera_id] if camera_id else []

    (sections, configs) = get_additional_structure(camera=bool(camera_id))
    
    set_func_values = collections.OrderedDict()
    for name, section in sections.iteritems():
        if not section.get('set'):
            continue
        
        if ('@_' + name) not in data:
            continue

        if section.get('get_set_dict'):
            set_func_values.setdefault(section['set'], {})[name] = data['@_' + name]

        else:
            set_func_values[section['set']] = data['@_' + name]

    for name, config in configs.iteritems():
        if not config.get('set'):
            continue

        if ('@_' + name) not in data:
            continue

        if config.get('get_set_dict'):
            set_func_values.setdefault(config['set'], {})[name] = data['@_' + name]
            
        else:
            set_func_values[config['set']] = data['@_' + name]

    for func, value in set_func_values.iteritems():
        func(*(args + [value]))

def create_system_uuid():
    return str(uuid.uuid4())

def encode_password(data):
    raw = pad(data)
    k = hashlib.md5(_main_config_cache['@application_uuid']).hexdigest()[:_BS]
    iv = Random.new().read(AES.block_size)
    cipher = AES.new(k, AES.MODE_CBC, iv)
    return base64.urlsafe_b64encode(iv + cipher.encrypt(raw))

def decode_password(data):
    k = hashlib.md5(_main_config_cache['@application_uuid']).hexdigest()[:_BS]
    clear = data
    coded = True
    try:
        e = base64.urlsafe_b64decode(data.encode('utf-8'))
        iv = e[:_BS]
        cipher = AES.new(k, AES.MODE_CBC, iv)
        clear = unpad(cipher.decrypt(e[_BS:]))
    except Exception as e:
        coded = False
        pass

    if coded == False:
        clear = data

    return clear

