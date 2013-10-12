
import base64
import json
import logging

from tornado.web import RequestHandler, HTTPError, asynchronous

import config
import mjpgclient
import motionctl
import remote
import template
import v4l2ctl


class BaseHandler(RequestHandler):
    def get_data(self):
        keys = self.request.arguments.keys()
        data = dict([(key, self.get_argument(key)) for key in keys])

        for key in self.request.files:
            files = self.request.files[key]
            if len(files) > 1:
                data[key] = files

            elif len(files) > 0:
                data[key] = files[0]

            else:
                continue

        return data
    
    def render(self, template_name, content_type='text/html', **context):
        self.set_header('Content-Type', content_type)
        
        context['USER'] = self.current_user
        
        content = template.render(template_name, **context)
        self.finish(content)
    
    def finish_json(self, data={}):
        self.set_header('Content-Type', 'application/json')
        self.finish(json.dumps(data))

    def get_current_user(self):
        try:
            scheme, token = self.request.headers.get('Authorization', '').split()
            if scheme.lower() == 'basic':
                user, pwd = base64.decodestring(token).split(':')
                main_config = config.get_main()
                
                if user == main_config.get('@admin_username') and pwd == main_config.get('@admin_password'):
                    return 'admin'
                
                elif user == main_config.get('@normal_username') and pwd == main_config.get('@normal_password'):
                    return 'normal'
                
        except:
            pass

        return None
    
    @staticmethod
    def auth(admin=False):
        def decorator(func):
            def wrapper(self, *args, **kwargs):
                user = self.current_user
                if (user is None) or (user != 'admin' and admin):
                    realm = 'motionEye admin authentication' if admin else 'motionEye authentication'
                    
                    self.set_status(401)
                    self.set_header('WWW-Authenticate', 'basic realm="%(realm)s"' % {
                            'realm': realm})
                    return self.finish('Authentication required.')
                
                return func(self, *args, **kwargs)
            
            return wrapper
        
        return decorator


class MainHandler(BaseHandler):
    @BaseHandler.auth()
    def get(self):
        self.render('main.html')


class ConfigHandler(BaseHandler):
    @asynchronous
    def get(self, camera_id=None, op=None):
        if camera_id is not None:
            camera_id = int(camera_id)
        
        if op == 'get':
            self.get_config(camera_id)
            
        elif op == 'list':
            self.list_cameras()
        
        elif op == 'list_devices':
            self.list_devices()
        
        else:
            raise HTTPError(400, 'unknown operation')
    
    @asynchronous
    def post(self, camera_id=None, op=None):
        if camera_id is not None:
            camera_id = int(camera_id)
        
        if op == 'set':
            self.set_config(camera_id)
        
        elif op == 'set_preview':
            self.set_preview(camera_id)
        
        elif op == 'add':
            self.add_camera()
        
        elif op == 'rem':
            self.rem_camera(camera_id)
        
        else:
            raise HTTPError(400, 'unknown operation')
    
    @BaseHandler.auth(admin=True)
    def get_config(self, camera_id):
        if camera_id:
            logging.debug('getting config for camera %(id)s' % {'id': camera_id})
            
            if camera_id not in config.get_camera_ids():
                raise HTTPError(404, 'no such camera')
            
            camera_config = config.get_camera(camera_id)
            if camera_config['@proto'] != 'v4l2':
                def on_response(remote_ui_config):
                    if remote_ui_config is None:
                        return self.finish_json({'error': True})
                    
                    tmp_config = self._camera_ui_to_dict(remote_ui_config)
                    tmp_config.update(camera_config)
                    ui_config = self._camera_dict_to_ui(tmp_config)
                    ui_config['available_resolutions'] = remote_ui_config['available_resolutions']
                    
                    self.finish_json(ui_config)
                
                remote.get_config(
                        camera_config.get('@host'),
                        camera_config.get('@port'),
                        camera_config.get('@username'),
                        camera_config.get('@password'),
                        camera_config.get('@remote_camera_id'), on_response)
            
            else:
                ui_config = self._camera_dict_to_ui(camera_config)
                
                resolutions = v4l2ctl.list_resolutions(camera_config['videodevice'])
                resolutions = [(str(w) + 'x' + str(h)) for (w, h) in resolutions]
                ui_config['available_resolutions'] = resolutions
                    
                self.finish_json(ui_config)
            
        else:
            logging.debug('getting main config')
            
            ui_config = self._main_dict_to_ui(config.get_main())
            self.finish_json(ui_config)
    
    @BaseHandler.auth(admin=True)
    def set_config(self, camera_id, ui_config=None, no_finish=False):
        if ui_config is None:
            try:
                ui_config = json.loads(self.request.body)
                
            except Exception as e:
                logging.error('could not decode json: %(msg)s' % {'msg': unicode(e)})
                
                raise
        
        if camera_id is not None:
            if camera_id == 0:
                logging.debug('setting multiple configs')
                
                for key, cfg in ui_config.items():
                    if key == 'main':
                        self.set_config(None, cfg, no_finish=True)
                        
                    else:
                        self.set_config(int(key), cfg, no_finish=True)

                return self.finish_json()
                 
            logging.debug('setting config for camera %(id)s' % {'id': camera_id})
            
            camera_ids = config.get_camera_ids()
            if camera_id not in camera_ids:
                raise HTTPError(404, 'no such camera')
            
            camera_config = config.get_camera(camera_id)
            if camera_config['@proto'] == 'v4l2':
                ui_config.setdefault('device', camera_config.get('videodevice', ''))
                ui_config.setdefault('proto', camera_config['@proto'])
                ui_config.setdefault('enabled', camera_config['@enabled'])
                
                camera_config = self._camera_ui_to_dict(ui_config)
                config.set_camera(camera_id, camera_config)
                
            else:  # remote camera
                # update the camera locally
                camera_config['@enabled'] = ui_config['enabled']
                config.set_camera(camera_id, camera_config)
                
                # remove the fields that should not get to the remote side
                del ui_config['device']
                del ui_config['proto']
                del ui_config['enabled']
                
                try:
                    remote.set_config(
                            camera_config.get('@host'),
                            camera_config.get('@port'),
                            camera_config.get('@username'),
                            camera_config.get('@password'),
                            camera_config.get('@remote_camera_id'),
                            ui_config)
                    
                except Exception as e:
                    return self.finish_json({'error': unicode(e)})       

        else:
            logging.debug('setting main config')
            
            main_config = self._main_ui_to_dict(ui_config)
            config.set_main(main_config)

        motionctl.restart()
        
        self.finish_json()

    @BaseHandler.auth(admin=True)
    def set_preview(self, camera_id):
        try:
            controls = json.loads(self.request.body)
            
        except Exception as e:
            logging.error('could not decode json: %(msg)s' % {'msg': unicode(e)})
            
            raise

        camera_config = config.get_camera(camera_id)
        if camera_config['@proto'] == 'v4l2': 
            device = camera_config['videodevice']
            
            if 'brightness' in controls:
                value = int(controls['brightness'])
                logging.debug('setting brightness to %(value)s...' % {'value': value})
    
                v4l2ctl.set_brightness(device, value)
    
            if 'contrast' in controls:
                value = int(controls['contrast'])
                logging.debug('setting contrast to %(value)s...' % {'value': value})
    
                v4l2ctl.set_contrast(device, value)
    
            if 'saturation' in controls:
                value = int(controls['saturation'])
                logging.debug('setting saturation to %(value)s...' % {'value': value})
    
                v4l2ctl.set_saturation(device, value)
    
            if 'hue' in controls:
                value = int(controls['hue'])
                logging.debug('setting hue to %(value)s...' % {'value': value})
    
                v4l2ctl.set_hue(device, value)
            
            self.finish_json({})

        else:
            def on_response(response):
                if response is None:
                    self.finish_json({'error': True})
                    
                else:
                    self.finish_json()
            
            remote.set_preview(
                    camera_config['@host'],
                    camera_config['@port'],
                    camera_config['@username'],
                    camera_config['@password'],
                    camera_config['@remote_camera_id'],
                    controls, on_response)

    @BaseHandler.auth()
    def list_cameras(self):
        logging.debug('listing cameras')

        host = self.get_argument('host', None)
        port = self.get_argument('port', None)
        username = self.get_argument('username', None)
        password = self.get_argument('password', None)
        
        if host:  # remote listing
            def on_response(cameras):
                if cameras is None:
                    self.finish_json({'error': True})
                    
                else:
                    self.finish_json({'cameras': cameras})
            
            cameras = remote.list_cameras(host, port, username, password, on_response)
                
        else:  # local listing
            cameras = []
            camera_ids = config.get_camera_ids()
            if not config.get_main().get('@enabled'):
                camera_ids = []
                
            length = [len(camera_ids)]
            def check_finished():
                if len(cameras) == length[0]:
                    self.finish_json({'cameras': cameras})
                    
            def on_response_builder(camera_id, camera_config):
                def on_response(remote_ui_config):
                    if remote_ui_config is None:
                        length[0] -= 1
                    
                    else:
                        remote_ui_config['id'] = camera_id
                        remote_ui_config['enabled'] = camera_config['@enabled']  # override the enabled status
                        cameras.append(remote_ui_config)
                        
                    check_finished()
                    
                return on_response
            
            for camera_id in camera_ids:
                camera_config = config.get_camera(camera_id)
                if camera_config['@proto'] == 'v4l2':
                    ui_config = self._camera_dict_to_ui(camera_config)
                    cameras.append(ui_config)
                    check_finished()

                else:  # remote camera
                    remote.get_config(
                            camera_config.get('@host'),
                            camera_config.get('@port'),
                            camera_config.get('@username'),
                            camera_config.get('@password'),
                            camera_config.get('@remote_camera_id'), on_response_builder(camera_id, camera_config))
            
            if length[0] == 0:        
                self.finish_json({'cameras': []})

    @BaseHandler.auth(admin=True)
    def list_devices(self):
        logging.debug('listing devices')
        
        configured_devices = {}
        for camera_id in config.get_camera_ids():
            data = config.get_camera(camera_id)
            if data['@proto'] == 'v4l2':
                configured_devices[data['videodevice']] = True

        devices = [{'device': d[0], 'name': d[1], 'configured': d[0] in configured_devices}
                for d in v4l2ctl.list_devices()]
        
        self.finish_json({'devices': devices})
    
    @BaseHandler.auth(admin=True)
    def add_camera(self):
        logging.debug('adding new camera')
        
        try:
            device_details = json.loads(self.request.body)
            
        except Exception as e:
            logging.error('could not decode json: %(msg)s' % {'msg': unicode(e)})
            
            raise

        proto = device_details['proto']
        if proto == 'v4l2':
            # find a suitable resolution
            for (w, h) in v4l2ctl.list_resolutions(device_details['device']):
                if w > 300:
                    device_details['width'] = w
                    device_details['height'] = h
                    break

        camera_id, camera_config = config.add_camera(device_details)
        camera_config['@id'] = camera_id

        if proto == 'v4l2':
            motionctl.restart()
            
            ui_config = self._camera_dict_to_ui(camera_config)
            resolutions = v4l2ctl.list_resolutions(camera_config['videodevice'])
            resolutions = [(str(w) + 'x' + str(h)) for (w, h) in resolutions]
            ui_config['available_resolutions'] = resolutions
            
            self.finish_json(ui_config)
        
        else:
            def on_response(remote_ui_config):
                if remote_ui_config is None:
                    self.finish_json({'error': True})
                
                tmp_config = self._camera_ui_to_dict(remote_ui_config)
                tmp_config.update(camera_config)
                ui_config = self._camera_dict_to_ui(tmp_config)
                ui_config['available_resolutions'] = remote_ui_config['available_resolutions']
                
                self.finish_json(ui_config)
                
            remote.get_config(
                    device_details.get('host'),
                    device_details.get('port'),
                    device_details.get('username'),
                    device_details.get('password'),
                    device_details.get('remote_camera_id'), on_response)
    
    @BaseHandler.auth(admin=True)
    def rem_camera(self, camera_id):
        logging.debug('removing camera %(id)s' % {'id': camera_id})
        
        local = config.get_camera(camera_id).get('@proto') == 'v4l2'
        config.rem_camera(camera_id)
        
        if local:
            motionctl.restart()
            
        self.finish_json()
        
    def _main_ui_to_dict(self, ui):
        return {
            '@enabled': ui.get('enabled', True),
            '@show_advanced': ui.get('show_advanced', False),
            '@admin_username': ui.get('admin_username', ''),
            '@admin_password': ui.get('admin_password', ''),
            '@normal_username': ui.get('normal_username', ''),
            '@normal_password': ui.get('normal_password', '')
        }

    def _main_dict_to_ui(self, data):
        return {
            'enabled': data.get('@enabled', True),
            'show_advanced': data.get('@show_advanced', False),
            'admin_username': data.get('@admin_username', ''),
            'admin_password': data.get('@admin_password', ''),
            'normal_username': data.get('@normal_username', ''),
            'normal_password': data.get('@normal_password', '')
        }

    def _camera_ui_to_dict(self, ui):
        if not ui.get('resolution'):  # avoid errors for empty resolution setting
            ui['resolution'] = '352x288'
    
        data = {
            # device
            '@name': ui.get('name', ''),
            '@enabled': ui.get('enabled', False),
            '@proto': ui.get('proto', 'v4l2'),
            'videodevice': ui.get('device', ''),
            'lightswitch': int(ui.get('light_switch_detect', False)) * 5,
            'auto_brightness': ui.get('auto_brightness', False),
            'brightness': max(1, int(round(int(ui.get('brightness', 0)) * 2.55))),
            'contrast': max(1, int(round(int(ui.get('contrast', 0)) * 2.55))),
            'saturation': max(1, int(round(int(ui.get('saturation', 0)) * 2.55))),
            'hue': max(1, int(round(int(ui.get('hue', 0)) * 2.55))),
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
            'webcam_quality': max(1, int(ui.get('streaming_quality', 75))),
            'webcam_motion': ui.get('streaming_motion', False),
            
            # still images
            'output_normal': False,
            'output_all': False,
            'output_motion': False,
            'snapshot_interval': 0,
            'jpeg_filename': '',
            'snapshot_filename': '',
            '@preserve_images': int(ui.get('preserve_images', 0)),
            
            # movies
            'ffmpeg_variable_bitrate': 2 + int((100 - int(ui.get('movie_quality', 75))) * 0.29),
            'ffmpeg_cap_new': ui.get('motion_movies', False),
            'movie_filename': ui.get('movie_file_name', '%Y-%m-%d-%H-%M-%S-%q'),
            '@preserve_movies': int(ui.get('preserve_movies', 0)),
        
            # motion detection
            'text_changes': ui.get('show_frame_changes', False),
            'locate': ui.get('show_frame_changes', False),
            'threshold': ui.get('frame_change_threshold', 1500),
            'noise_tune': ui.get('auto_noise_detect', True),
            'noise_level': max(1, int(int(ui.get('noise_level', 8)) * 2.55)),
            'gap': int(ui.get('gap', 60)),
            'pre_capture': int(ui.get('pre_capture', 0)),
            'post_capture': int(ui.get('post_capture', 0)),
            
            # motion notifications
            '@motion_notifications': ui.get('motion_notifications', False),
            '@motion_notifications_emails': ui.get('motion_notifications_emails', ''),
            
            # working schedule
            '@working_schedule': ''
        }
        
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
        
        if not ui.get('video_streaming', True):
            data['webcam_maxrate'] = 5
            data['webcam_quality'] = 75
    
        if ui.get('still_images', False):
            capture_mode = ui.get('capture_mode', 'motion-triggered')
            if capture_mode == 'motion-triggered':
                data['output_normal'] = True
                data['jpeg_filename'] = ui.get('image_file_name', '%Y-%m-%d-%H-%M-%S-%q')  
                
            elif capture_mode == 'interval-snapshots':
                data['snapshot_interval'] = int(ui.get('snapshot_interval', 300))
                data['snapshot_filename'] = ui.get('image_file_name', '%Y-%m-%d-%H-%M-%S-%q')
                
            elif capture_mode == 'all-frames':
                data['output_all'] = True
                data['jpeg_filename'] = ui.get('image_file_name', '%Y-%m-%d-%H-%M-%S')
                
            data['quality'] = max(1, int(ui.get('image_quality', 75)))
            
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
        
    def _camera_dict_to_ui(self, data):
        if data['@proto'] == 'v4l2':
            device_uri = data['videodevice']
        
        else:
            device_uri = '%(host)s:%(port)s/config/%(camera_id)s' % {
                    'username': data['@username'],
                    'password': '***',
                    'host': data['@host'],
                    'port': data['@port'],
                    'camera_id': data['@remote_camera_id']}
        
        ui = {
            # device
            'name': data['@name'],
            'enabled': data['@enabled'],
            'id': data.get('@id'),
            'proto': data['@proto'],
            'device': device_uri,
            'light_switch_detect': data.get('lightswitch') > 0,
            'auto_brightness': data.get('auto_brightness'),
            'brightness': int(round(int(data.get('brightness')) / 2.55)),
            'contrast': int(round(int(data.get('contrast')) / 2.55)),
            'saturation': int(round(int(data.get('saturation')) / 2.55)),
            'hue': int(round(int(data.get('hue')) / 2.55)),
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
            
            # text overlay
            'text_overlay': False,
            'left_text': 'camera-name',
            'right_text': 'timestamp',
            'custom_left_text': '',
            'custom_right_text': '',
            
            # streaming
            'vudeo_streaming': not data.get('webcam_localhost'),
            'streaming_port': int(data.get('webcam_port')),
            'streaming_framerate': int(data.get('webcam_maxrate')),
            'streaming_quality': int(data.get('webcam_quality')),
            'streaming_motion': int(data.get('webcam_motion')),
            
            # still images
            'still_images': False,
            'capture_mode': 'motion-triggered',
            'image_file_name': '%Y-%m-%d-%H-%M-%S',
            'image_quality': 75,
            'snapshot_interval': 0,
            'preserve_images': data['@preserve_images'],
            
            # motion movies
            'motion_movies': data.get('ffmpeg_cap_new'),
            'movie_quality': int((max(2, data.get('ffmpeg_variable_bitrate')) - 2) / 0.29),
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
                
            elif data.get('snapshot_interval'):
                ui['capture-mode'] = 'interval-snapshots'
                ui['image_file_name'] = snapshot_filename
                ui['snapshot_interval'] = snapshot_interval
                
            elif data.get('output_normal'):
                ui['capture-mode'] = 'motion-triggered'
                ui['image_file_name'] = jpeg_filename  
                
            ui['image_quality'] = ui.get('quality', 75)
        
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


class SnapshotHandler(BaseHandler):
    @asynchronous
    def get(self, camera_id, op, filename=None):
        if camera_id is not None:
            camera_id = int(camera_id)
            if camera_id not in config.get_camera_ids():
                raise HTTPError(404, 'no such camera')
        
        if op == 'current':
            self.current(camera_id)
            
        elif op == 'list':
            self.list(camera_id)
            
        elif op == 'download':
            self.download(camera_id, filename)
        
        else:
            raise HTTPError(400, 'unknown operation')
    
    @BaseHandler.auth()
    def current(self, camera_id):
        camera_config = config.get_camera(camera_id)
        if camera_config['@proto'] == 'v4l2':
            jpg = mjpgclient.get_jpg(camera_id)
            if jpg is None:
                return self.finish()
        
            self.set_header('Content-Type', 'image/jpeg')
            self.finish(jpg)
        
        else:
            def on_response(jpg):
                if jpg is None:
                    self.finish({})
                    
                else:
                    self.set_header('Content-Type', 'image/jpeg')
                    self.finish(jpg)
            
            remote.current_snapshot(
                    camera_config['@host'],
                    camera_config['@port'],
                    camera_config['@username'],
                    camera_config['@password'],
                    camera_config['@remote_camera_id'], on_response)
                
    @BaseHandler.auth()
    def list(self, camera_id):
        logging.debug('listing snapshots for camera %(id)s' % {'id': camera_id})
        
        # TODO implement me
        
        self.finish_json()
    
    @BaseHandler.auth()
    def download(self, camera_id, filename):
        logging.debug('downloading snapshot %(filename)s of camera %(id)s' % {
                'filename': filename, 'id': camera_id})
        
        # TODO implement me
        
        self.finish_json()


class MovieHandler(BaseHandler):
    @asynchronous
    def get(self, camera_id, op, filename=None):
        if op == 'list':
            self.list(camera_id)
            
        elif op == 'download':
            self.download(camera_id, filename)
        
        else:
            raise HTTPError(400, 'unknown operation')

    @BaseHandler.auth()    
    def list(self, camera_id):
        logging.debug('listing movies for camera %(id)s' % {'id': camera_id})

        # TODO implement me
        
        self.finish_json()
    
    @BaseHandler.auth()
    def download(self, camera_id, filename):
        logging.debug('downloading movie %(filename)s of camera %(id)s' % {
                'filename': filename, 'id': camera_id})

        # TODO implement me
        
        self.finish_json()
