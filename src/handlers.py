
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
                
                else:
                    logging.error('authentication failed for user %(user)s' % {'user': user})
                
        except:
            pass

        return None
    
    @staticmethod
    def auth(admin=False, prompt=True):
        def decorator(func):
            def wrapper(self, *args, **kwargs):
                user = self.current_user
                if (user is None) or (user != 'admin' and admin):
                    realm = 'motionEye admin authentication' if admin else 'motionEye authentication'
                    
                    self.set_status(401)
                    if prompt:
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
                    camera_url = remote.make_remote_camera_url(
                            camera_config.get('@host'),
                            camera_config.get('@port'),
                            camera_config.get('@remote_camera_id'))
                    
                    camera_full_url = camera_config['@proto'] + '://' + camera_url
                    
                    if remote_ui_config is None:
                        return self.finish_json({'error': 'Failed to get remote camera configuration for %(url)s.' % {
                                'url': camera_full_url}})
                    
                    for key, value in camera_config.items():
                        remote_ui_config[key.replace('@', '')] = value
                    
                    remote_ui_config['device'] = camera_url
                    
                    self.finish_json(remote_ui_config)
                
                remote.get_config(
                        camera_config.get('@host'),
                        camera_config.get('@port'),
                        camera_config.get('@username'),
                        camera_config.get('@password'),
                        camera_config.get('@remote_camera_id'), on_response)
            
            else:
                ui_config = config.camera_dict_to_ui(camera_config)
                
                resolutions = v4l2ctl.list_resolutions(camera_config['videodevice'])
                resolutions = [(str(w) + 'x' + str(h)) for (w, h) in resolutions]
                ui_config['available_resolutions'] = resolutions
                    
                self.finish_json(ui_config)
            
        else:
            logging.debug('getting main config')
            
            ui_config = config.main_dict_to_ui(config.get_main())
            self.finish_json(ui_config)
    
    @BaseHandler.auth(admin=True)
    def set_config(self, camera_id, ui_config=None, no_finish=False):
        if ui_config is None:
            try:
                ui_config = json.loads(self.request.body)
                
            except Exception as e:
                logging.error('could not decode json: %(msg)s' % {'msg': unicode(e)})
                
                raise
            
        reload = False
        
        if camera_id is not None:
            if camera_id == 0:
                logging.debug('setting multiple configs')
                
                for key, cfg in ui_config.items():
                    if key == 'main':
                        reload = self.set_config(None, cfg, no_finish=True) or reload
                        
                    else:
                        reload = self.set_config(int(key), cfg, no_finish=True) or reload

                return self.finish_json({'reload': reload})
                 
            logging.debug('setting config for camera %(id)s' % {'id': camera_id})
            
            camera_ids = config.get_camera_ids()
            if camera_id not in camera_ids:
                raise HTTPError(404, 'no such camera')
            
            camera_config = config.get_camera(camera_id)
            if camera_config['@proto'] == 'v4l2':
                ui_config.setdefault('device', camera_config.get('videodevice', ''))
                ui_config.setdefault('proto', camera_config['@proto'])
                ui_config.setdefault('enabled', camera_config['@enabled'])
                
                camera_config = config.camera_ui_to_dict(ui_config)
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
                    logging.error('failed to set remote camera config: %(msg)s' % {'msg': unicode(e)})
                    
                    if not no_finish:
                        return self.finish_json({'error': unicode(e)})       

        else:
            logging.debug('setting main config')
            
            old_main_config = config.get_main()
            old_admin_credentials = old_main_config.get('@admin_username', '') + ':' + old_main_config.get('@admin_password', '')
            
            main_config = config.main_ui_to_dict(ui_config)
            admin_credentials = main_config.get('@admin_username', '') + ':' + main_config.get('@admin_password', '')
            
            config.set_main(main_config)
            
            if admin_credentials != old_admin_credentials:
                logging.debug('admin credentials changed, reload needed')
                
                reload = True 

        motionctl.restart()
        
        if not no_finish:
            self.finish_json()
        
        return reload

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
                    self.finish_json({'error': 'Failed to list remote cameras.'})
                    
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
                        camera_url = remote.make_remote_camera_url(
                                camera_config.get('@host'),
                                camera_config.get('@port'),
                                camera_config.get('@remote_camera_id'),
                                camera_config.get('@proto'))
                        
                        cameras.append({
                            'id': camera_id,
                            'name': '&lt;' + camera_url + '&gt;',
                            'enabled': False,
                            'streaming_framerate': 1,
                            'framerate': 1
                        })
                    
                    else:
                        remote_ui_config['id'] = camera_id
                        remote_ui_config['enabled'] = camera_config['@enabled']  # override the enabled status
                        cameras.append(remote_ui_config)
                        
                    check_finished()
                    
                return on_response
            
            for camera_id in camera_ids:
                camera_config = config.get_camera(camera_id)
                if camera_config['@proto'] == 'v4l2':
                    ui_config = config.camera_dict_to_ui(camera_config)
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
                    # compute the ffmpeg bps
                    
                    max_val = w * h * 2 / 3
                    max_val = min(max_val, 9999999)
                    val = max_val * 75 / 100
                    device_details['ffmpeg_bps'] = val

                    break

        camera_id, camera_config = config.add_camera(device_details)
        camera_config['@id'] = camera_id

        if proto == 'v4l2':
            motionctl.restart()
            
            ui_config = config.camera_dict_to_ui(camera_config)
            resolutions = v4l2ctl.list_resolutions(camera_config['videodevice'])
            resolutions = [(str(w) + 'x' + str(h)) for (w, h) in resolutions]
            ui_config['available_resolutions'] = resolutions
            
            self.finish_json(ui_config)
        
        else:
            def on_response(remote_ui_config):
                if remote_ui_config is None:
                    self.finish_json({'error': True})
                
                tmp_config = config.camera_ui_to_dict(remote_ui_config)
                tmp_config.update(camera_config)
                ui_config = config.camera_dict_to_ui(tmp_config)
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
    
    @BaseHandler.auth(prompt=False)
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
