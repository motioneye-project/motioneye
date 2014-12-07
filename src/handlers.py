
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

import base64
import datetime
import json
import logging
import os
import re
import socket

from tornado.web import RequestHandler, HTTPError, asynchronous
from tornado.ioloop import IOLoop

import config
import mediafiles
import motionctl
import powerctl
import remote
import settings
import smbctl
import template
import update
import utils
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
        import motioneye
        
        self.set_header('Content-Type', content_type)
        
        context['USER'] = self.current_user
        context['VERSION'] = motioneye.VERSION
        
        content = template.render(template_name, **context)
        self.finish(content)
    
    def finish_json(self, data={}):
        self.set_header('Content-Type', 'application/json')
        self.finish(json.dumps(data))

    def get_current_user(self):
        main_config = config.get_main()
        
        try:
            scheme, token = self.request.headers.get('Authorization', '').split()
            if scheme.lower() == 'basic':
                user, pwd = base64.decodestring(token).split(':')
                
                if user == main_config.get('@admin_username') and pwd == main_config.get('@admin_password'):
                    return 'admin'
                
                elif user == main_config.get('@normal_username') and pwd == main_config.get('@normal_password'):
                    return 'normal'
                
                else:
                    logging.error('authentication failed for user %(user)s' % {'user': user})
                
        except: # no authentication info provided
            if not main_config.get('@normal_password') and not self.get_argument('logout', None):
                return 'normal'

        return None
    
    def _handle_request_exception(self, exception):
        try:
            if isinstance(exception, HTTPError):
                logging.error(str(exception))
                self.set_status(exception.status_code)
                self.finish_json({'error': exception.log_message or getattr(exception, 'reason', None) or str(exception)})
            
            else:
                logging.error(str(exception), exc_info=True)
                self.set_status(500)
                self.finish_json({'error':  'internal server error'})
                
        except RuntimeError:
            pass # nevermind
        
    @staticmethod
    def auth(admin=False, prompt=True):
        def decorator(func):
            def wrapper(self, *args, **kwargs):
                user = self.current_user
                if (user is None) or (user != 'admin' and admin):
                    self.set_status(401)
                    if prompt:
                        self.set_header('WWW-Authenticate', 'basic realm="%(realm)s"' % {
                                'realm': 'motionEye authentication'})
                        
                    return self.finish('Authentication required.')
                
                return func(self, *args, **kwargs)
            
            return wrapper
        
        return decorator

    def get(self, *args, **kwargs):
        raise HTTPError(400, 'method not allowed')

    def post(self, *args, **kwargs):
        raise HTTPError(400, 'method not allowed')


class NotFoundHandler(BaseHandler):
    def get(self):
        raise HTTPError(404, 'not found')

    def post(self):
        raise HTTPError(404, 'not found')


class MainHandler(BaseHandler):
    @BaseHandler.auth()
    def get(self):
        if self.get_argument('logout', None):
            return self.redirect('/')
        
        timezones = []
        if settings.LOCAL_TIME_FILE:
            import pytz
            timezones = pytz.common_timezones

        self.render('main.html',
                wpa_supplicant=settings.WPA_SUPPLICANT_CONF,
                enable_reboot=settings.ENABLE_REBOOT,
                timezones=timezones,
                hostname=socket.gethostname())


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
        
        elif op == '_relay_event':
            self._relay_event(camera_id)
        
        else:
            raise HTTPError(400, 'unknown operation')
    
    @BaseHandler.auth(admin=True)
    def get_config(self, camera_id):
        if camera_id:
            logging.debug('getting config for camera %(id)s' % {'id': camera_id})
            
            if camera_id not in config.get_camera_ids():
                raise HTTPError(404, 'no such camera')
            
            local_config = config.get_camera(camera_id)
            if utils.local_camera(local_config):
                ui_config = config.camera_dict_to_ui(local_config)
                    
                self.finish_json(ui_config)
            
            else:
                def on_response(remote_ui_config=None, error=None):
                    if error:
                        return self.finish_json({'error': 'Failed to get remote camera configuration for %(url)s: %(msg)s.' % {
                                'url': remote.make_camera_url(local_config), 'msg': error}})
                    
                    for key, value in local_config.items():
                        remote_ui_config[key.replace('@', '')] = value
                    
                    self.finish_json(remote_ui_config)
                
                remote.get_config(local_config, on_response)
            
        else:
            logging.debug('getting main config')
            
            ui_config = config.main_dict_to_ui(config.get_main())
            self.finish_json(ui_config)
    
    @BaseHandler.auth(admin=True)
    def set_config(self, camera_id):
        try:
            ui_config = json.loads(self.request.body)
            
        except Exception as e:
            logging.error('could not decode json: %(msg)s' % {'msg': unicode(e)})
            
            raise
        
        camera_ids = config.get_camera_ids()
        
        def set_camera_config(camera_id, ui_config, on_finish):
            logging.debug('setting config for camera %(id)s...' % {'id': camera_id})
            
            if camera_id not in camera_ids:
                raise HTTPError(404, 'no such camera')
            
            local_config = config.get_camera(camera_id)
            if utils.local_camera(local_config):
                # certain parameters cannot be changed via ui_config;
                # we must preserve existing values for those params
                local_ui_config = config.camera_dict_to_ui(local_config)
                ui_config.setdefault('enabled', local_ui_config['enabled'])
                ui_config['proto'] = local_ui_config['proto']
                ui_config['host'] = local_ui_config['host']
                ui_config['port'] = local_ui_config['port']
                ui_config['uri'] = local_ui_config['uri']
                ui_config['username'] = local_ui_config['username']
                ui_config['password'] = local_ui_config['password']
                
                local_config = config.camera_ui_to_dict(ui_config)
                config.set_camera(camera_id, local_config)
            
                on_finish(None, True) # (no error, motion needs restart)

            else: # remote camera
                # update the camera locally
                local_config['@enabled'] = ui_config['enabled']
                config.set_camera(camera_id, local_config)
                
                # when the local_config supplied has only the enabled state,
                # the camera was probably disabled due to errors

                if ui_config.has_key('name'):
                    def on_finish_wrapper(error=None):
                        return on_finish(error, False)
                    
                    remote.set_config(local_config, ui_config, on_finish_wrapper)
                
                else:
                    on_finish(None, False)

        def set_main_config(ui_config):
            logging.debug('setting main config...')
            
            old_main_config = config.get_main()
            old_admin_credentials = old_main_config.get('@admin_username', '') + ':' + old_main_config.get('@admin_password', '')
            
            main_config = config.main_ui_to_dict(ui_config)
            main_config.setdefault('thread', old_main_config.get('thread', [])) 
            admin_credentials = main_config.get('@admin_username', '') + ':' + main_config.get('@admin_password', '')
            
            wifi_changed = bool([k for k in ['@wifi_enabled', '@wifi_name', '@wifi_key'] if old_main_config.get(k) != main_config.get(k)])
            
            config.set_main(main_config)
            
            reboot = False
            reload = False
            
            if admin_credentials != old_admin_credentials:
                logging.debug('admin credentials changed, reload needed')
                
                reload = True
            
            if wifi_changed:
                logging.debug('wifi settings changed, reboot needed')
                
                reboot = True
                
            return {'reload': reload, 'reboot': reboot}
        
        reload = False # indicates that browser should reload the page
        reboot = [False] # indicates that the server will reboot immediately
        restart = [False]  # indicates that the local motion instance was modified and needs to be restarted
        error = [None]
        
        def finish():
            if reboot[0]:
                if settings.ENABLE_REBOOT:
                    def call_reboot():
                        logging.info('rebooting')
                        os.system('reboot')
                    
                    ioloop = IOLoop.instance()
                    ioloop.add_timeout(datetime.timedelta(seconds=2), call_reboot)
                    return self.finish({'reload': False, 'reboot': True, 'error': None})
                
                else:
                    reboot[0] = False

            if restart[0]:
                logging.debug('motion needs to be restarted')
                
                motionctl.stop()
                
                if settings.SMB_SHARES:
                    logging.debug('updating SMB mounts')
                    stop, start = smbctl.update_mounts()  # @UnusedVariable

                    if start:
                        motionctl.start()
                
                else:
                    motionctl.start()

            self.finish({'reload': reload, 'reboot': reboot[0], 'error': error[0]})
        
        if camera_id is not None:
            if camera_id == 0: # multiple camera configs
                if len(ui_config) > 1:
                    logging.debug('setting multiple configs')
                
                elif len(ui_config) == 0:
                    logging.warn('no configuration to set')
                    
                    self.finish()
                
                so_far = [0]
                def check_finished(e, r):
                    restart[0] = restart[0] or r
                    error[0] = error[0] or e
                    so_far[0] += 1
                    
                    if so_far[0] >= len(ui_config): # finished
                        finish()
        
                for key, cfg in ui_config.items():
                    if key == 'main':
                        result = set_main_config(cfg)
                        reload = result['reload'] or reload
                        reboot[0] = result['reboot'] or reboot[0]
                        check_finished(None, reload)
                        
                    else:
                        set_camera_config(int(key), cfg, check_finished)
            
            else: # single camera config
                def on_finish(e, r):
                    error[0] = e
                    restart[0] = r
                    finish()

                set_camera_config(camera_id, ui_config, on_finish)

        else: # main config
            result = set_main_config(ui_config)
            reload = result['reload']
            reboot[0] = result['reboot']

    @BaseHandler.auth(admin=True)
    def set_preview(self, camera_id):
        try:
            controls = json.loads(self.request.body)
            
        except Exception as e:
            logging.error('could not decode json: %(msg)s' % {'msg': unicode(e)})
            
            raise

        camera_config = config.get_camera(camera_id)
        if utils.v4l2_camera(camera_config): 
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

        elif utils.remote_camera(camera_config):
            def on_response(error=None):
                if error:
                    self.finish_json({'error': error})
                    
                else:
                    self.finish_json()
            
            remote.set_preview(camera_config, controls, on_response)
        
        else:
            self.finish_json({'error': True})

    @BaseHandler.auth()
    def list_cameras(self):
        logging.debug('listing cameras')

        type = self.get_data().get('type')        
        if type == 'motioneye':  # remote listing
            def on_response(cameras=None, error=None):
                if error:
                    self.finish_json({'error': error})
                    
                else:
                    cameras = [c for c in cameras if c.get('enabled')]
                    self.finish_json({'cameras': cameras})
            
            remote.list_cameras(self.get_data(), on_response)
        
        elif type == 'netcam':
            def on_response(cameras=None, error=None):
                if error:
                    self.finish_json({'error': error})
                    
                else:
                    self.finish_json({'cameras': cameras})
            
            utils.test_netcam_url(self.get_data(), on_response)
                
        else:  # assuming local listing
            cameras = []
            camera_ids = config.get_camera_ids()
            if not config.get_main().get('@enabled'):
                camera_ids = []
                
            length = [len(camera_ids)]
            def check_finished():
                if len(cameras) == length[0]:
                    cameras.sort(key=lambda c: c['id'])
                    self.finish_json({'cameras': cameras})
                    
            def on_response_builder(camera_id, local_config):
                def on_response(remote_ui_config=None, error=None):
                    if error:
                        cameras.append({
                            'id': camera_id,
                            'name': '&lt;' + remote.make_camera_url(local_config) + '&gt;',
                            'enabled': False,
                            'streaming_framerate': 1,
                            'framerate': 1
                        })
                    
                    else:
                        remote_ui_config['id'] = camera_id
                        
                        if not remote_ui_config['enabled'] and local_config['@enabled']:
                            # if a remote camera is disabled, make sure it's disabled locally as well
                            local_config['@enabled'] = False
                            config.set_camera(camera_id, local_config)
                        
                        elif remote_ui_config['enabled'] and not local_config['@enabled']:
                            # if a remote camera is locally disabled, make sure the remote config says the same thing
                            remote_ui_config['enabled'] = False
                            
                        for key, value in local_config.items():
                            remote_ui_config[key.replace('@', '')] = value

                        cameras.append(remote_ui_config)
                        
                    check_finished()
                    
                return on_response
            
            for camera_id in camera_ids:
                local_config = config.get_camera(camera_id)
                if local_config is None:
                    continue
                
                if utils.local_camera(local_config):
                    ui_config = config.camera_dict_to_ui(local_config)
                    cameras.append(ui_config)
                    check_finished()

                else:  # remote camera
                    if local_config.get('@enabled'):
                        remote.get_config(local_config, on_response_builder(camera_id, local_config))
                    
                    else: # don't try to reach the remote of the camera is disabled
                        on_response_builder(camera_id, local_config)(None)
            
            if length[0] == 0:        
                self.finish_json({'cameras': []})

    @BaseHandler.auth(admin=True)
    def list_devices(self):
        logging.debug('listing devices')
        
        configured_devices = {}
        for camera_id in config.get_camera_ids():
            data = config.get_camera(camera_id)
            if utils.v4l2_camera(data):
                configured_devices[data['videodevice']] = True

        devices = [{'uri': d[0], 'name': d[1], 'configured': d[0] in configured_devices}
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
            for (w, h) in v4l2ctl.list_resolutions(device_details['uri']):
                if w > 300:
                    device_details.setdefault('resolution', str(w) + 'x' + str(h))
                    break
                
        else:
            # adjust uri format
            if device_details['uri'] and not device_details['uri'].startswith('/'):
                device_details['uri'] = '/' + device_details['uri']
            while device_details['uri'] and device_details['uri'].endswith('/'):
                device_details['uri'] = device_details['uri'][:-1]

        camera_id, camera_config = config.add_camera(device_details)
        camera_config['@id'] = camera_id

        if utils.local_camera(camera_config):
            motionctl.stop()
            
            if settings.SMB_SHARES:
                stop, start = smbctl.update_mounts()  # @UnusedVariable

                if start:
                    motionctl.start()
            
            else:
                motionctl.start()
            
            ui_config = config.camera_dict_to_ui(camera_config)
            
            self.finish_json(ui_config)
        
        else: # remote camera
            def on_response(remote_ui_config=None, error=None):
                if error:
                    self.finish_json({'error': error})

                for key, value in camera_config.items():
                    remote_ui_config[key.replace('@', '')] = value
                
                self.finish_json(remote_ui_config)
                
            remote.get_config(device_details, on_response)
    
    @BaseHandler.auth(admin=True)
    def rem_camera(self, camera_id):
        logging.debug('removing camera %(id)s' % {'id': camera_id})
        
        local = utils.local_camera(config.get_camera(camera_id))
        config.rem_camera(camera_id)
        
        if local:
            motionctl.stop()
            motionctl.start()
            
        self.finish_json()

    @BaseHandler.auth(admin=True)
    def _relay_event(self, camera_id):
        event = self.get_argument('event')
        logging.debug('event %(event)s relayed for camera %(id)s' % {'event': event, 'id': camera_id})
        
        if event == 'start':
            motionctl._motion_detected[camera_id] = True
            
        elif event == 'stop':
            motionctl._motion_detected[camera_id] = False
            
        else:
            logging.warn('unknown event %s' % event)

        self.finish_json()


class PictureHandler(BaseHandler):
    @asynchronous
    def get(self, camera_id, op, filename=None, group=None):
        if camera_id is not None:
            camera_id = int(camera_id)
            if camera_id not in config.get_camera_ids():
                raise HTTPError(404, 'no such camera')
        
        if op == 'current':
            self.current(camera_id)
            
        elif op == 'list':
            self.list(camera_id)
            
        elif op == 'frame':
            self.frame(camera_id)
            
        elif op == 'download':
            self.download(camera_id, filename)
        
        elif op == 'preview':
            self.preview(camera_id, filename)
        
        elif op == 'zipped':
            self.zipped(camera_id, group)
        
        elif op == 'timelapse':
            self.timelapse(camera_id, group)
        
        else:
            raise HTTPError(400, 'unknown operation')
    
    @asynchronous
    def post(self, camera_id, op, filename=None, group=None):
        if camera_id is not None:
            camera_id = int(camera_id)
            if camera_id not in config.get_camera_ids():
                raise HTTPError(404, 'no such camera')
        
        if op == 'delete':
            self.delete(camera_id, filename)

        else:
            raise HTTPError(400, 'unknown operation')
    
    @BaseHandler.auth(prompt=False)
    def current(self, camera_id):
        self.set_header('Content-Type', 'image/jpeg')
        
        sequence = self.get_argument('seq', None)
        if sequence:
            sequence = int(sequence)
        
        width = self.get_argument('width', None)
        height = self.get_argument('height', None)
        
        picture = sequence and mediafiles.get_picture_cache(camera_id, sequence, width) or None

        if picture is not None:
            return self.try_finish(picture)

        camera_config = config.get_camera(camera_id)
        if utils.local_camera(camera_config):
            picture = mediafiles.get_current_picture(camera_config,
                    width=width,
                    height=height)
            
            if sequence and picture:
                mediafiles.set_picture_cache(camera_id, sequence, width, picture)

            self.set_cookie('motion_detected_' + str(camera_id), str(motionctl.is_motion_detected(camera_id)).lower())
            self.try_finish(picture)
                
        else: # remote camera
            def on_response(motion_detected=False, picture=None, error=None):
                if sequence and picture:
                    mediafiles.set_picture_cache(camera_id, sequence, width, picture)
                
                self.set_cookie('motion_detected_' + str(camera_id), str(motion_detected).lower())
                self.try_finish(picture)
            
            remote.get_current_picture(camera_config, on_response, width=width, height=height)

    @BaseHandler.auth()
    def list(self, camera_id):
        logging.debug('listing pictures for camera %(id)s' % {'id': camera_id})
        
        camera_config = config.get_camera(camera_id)
        if utils.local_camera(camera_config):
            def on_media_list(media_list):
                if media_list is None:
                    return self.finish_json({'error': 'Failed to get pictures list.'})

                self.finish_json({
                    'mediaList': media_list,
                    'cameraName': camera_config['@name']
                })
            
            mediafiles.list_media(camera_config, media_type='picture',
                    callback=on_media_list, prefix=self.get_argument('prefix', None))

        else: # remote camera
            def on_response(remote_list=None, error=None):
                if error:
                    return self.finish_json({'error': 'Failed to get picture list for %(url)s: %(msg)s.' % {
                            'url': remote.make_camera_url(camera_config), 'msg': error}})

                self.finish_json(remote_list)
            
            remote.list_media(camera_config, on_response, media_type='picture', prefix=self.get_argument('prefix', None))

    @BaseHandler.auth()
    def frame(self, camera_id):
        camera_config = config.get_camera(camera_id)
        
        if utils.local_camera(camera_config) or self.get_argument('title', None) is not None:
            self.render('frame.html',
                    camera_id=camera_id,
                    camera_config=camera_config,
                    title=self.get_argument('title', camera_config.get('@name', '')))

        else: # remote camera, we need to fetch remote config
            def on_response(remote_ui_config=None, error=None):
                if error:
                    return self.render('frame.html',
                            camera_id=camera_id,
                            camera_config=camera_config,
                            title=self.get_argument('title', ''))

                remote_config = config.camera_ui_to_dict(remote_ui_config)
                self.render('frame.html',
                        camera_id=camera_id,
                        camera_config=remote_config,
                        title=self.get_argument('title', remote_config['@name']))

            remote.get_config(camera_config, on_response)


    @BaseHandler.auth()
    def download(self, camera_id, filename):
        logging.debug('downloading picture %(filename)s of camera %(id)s' % {
                'filename': filename, 'id': camera_id})
        
        camera_config = config.get_camera(camera_id)
        if utils.local_camera(camera_config):
            content = mediafiles.get_media_content(camera_config, filename, 'picture')
            
            pretty_filename = camera_config['@name'] + '_' + os.path.basename(filename)
            self.set_header('Content-Type', 'image/jpeg')
            self.set_header('Content-Disposition', 'attachment; filename=' + pretty_filename + ';')
            
            self.finish(content)
        
        else: # remote camera
            def on_response(response=None, error=None):
                if error:
                    return self.finish_json({'error': 'Failed to download picture from %(url)s: %(msg)s.' % {
                            'url': remote.make_camera_url(camera_config), 'msg': error}})

                pretty_filename = os.path.basename(filename) # no camera name available w/o additional request
                self.set_header('Content-Type', 'image/jpeg')
                self.set_header('Content-Disposition', 'attachment; filename=' + pretty_filename + ';')
                
                self.finish(response)

            remote.get_media_content(camera_config, on_response, filename=filename, media_type='picture')

    @BaseHandler.auth()
    def preview(self, camera_id, filename):
        logging.debug('previewing picture %(filename)s of camera %(id)s' % {
                'filename': filename, 'id': camera_id})
        
        camera_config = config.get_camera(camera_id)
        if utils.local_camera(camera_config):
            content = mediafiles.get_media_preview(camera_config, filename, 'picture',
                    width=self.get_argument('width', None),
                    height=self.get_argument('height', None))
            
            if content:
                self.set_header('Content-Type', 'image/jpeg')
                
            else:
                self.set_header('Content-Type', 'image/svg+xml')
                content = open(os.path.join(settings.STATIC_PATH, 'img', 'no-preview.svg')).read()
                
            self.finish(content)
        
        else:
            def on_response(content=None, error=None):
                if content:
                    self.set_header('Content-Type', 'image/jpeg')
                    
                else:
                    self.set_header('Content-Type', 'image/svg+xml')
                    content = open(os.path.join(settings.STATIC_PATH, 'img', 'no-preview.svg')).read()
                
                self.finish(content)
            
            remote.get_media_preview(camera_config, on_response, filename=filename, media_type='picture',
                    width=self.get_argument('width', None),
                    height=self.get_argument('height', None))
    
    @BaseHandler.auth()
    def delete(self, camera_id, filename):
        logging.debug('deleting picture %(filename)s of camera %(id)s' % {
                'filename': filename, 'id': camera_id})
        
        camera_config = config.get_camera(camera_id)
        if utils.local_camera(camera_config):
            try:
                mediafiles.del_media_content(camera_config, filename, 'picture')
                self.finish_json()
                
            except Exception as e:
                self.finish_json({'error': unicode(e)})

        else: # remote camera
            def on_response(response=None, error=None):
                if error:
                    return self.finish_json({'error': 'Failed to delete picture from %(url)s: %(msg)s.' % {
                            'url': remote.make_camera_url(camera_config), 'msg': error}})

                self.finish_json()

            remote.del_media_content(camera_config, on_response, filename=filename, media_type='picture')

    @BaseHandler.auth()
    def zipped(self, camera_id, group):
        key = self.get_argument('key', None)
        if key:
            logging.debug('serving zip file for group %(group)s of camera %(id)s with key %(key)s' % {
                    'group': group, 'id': camera_id, 'key': key})
            
            data = mediafiles.get_prepared_cache(key)
            if not data:
                logging.error('prepared cache data for key "%s" does not exist' % key)
                
                raise HTTPError(404, 'no such key')

            camera_config = config.get_camera(camera_id)
            if utils.local_camera(camera_config):
                pretty_filename = camera_config['@name'] + '_' + group
                pretty_filename = re.sub('[^a-zA-Z0-9]', '_', pretty_filename)
     
            else: # remote camera
                pretty_filename = re.sub('[^a-zA-Z0-9]', '_', group)

            self.set_header('Content-Type', 'application/zip')
            self.set_header('Content-Disposition', 'attachment; filename=' + pretty_filename + '.zip;')
            self.finish(data)

        else:
            logging.debug('preparing zip file for group %(group)s of camera %(id)s' % {
                    'group': group, 'id': camera_id})

            camera_config = config.get_camera(camera_id)
            if utils.local_camera(camera_config):
                def on_zip(data):
                    if data is None:
                        return self.finish_json({'error': 'Failed to create zip file.'})
    
                    key = mediafiles.set_prepared_cache(data)
                    logging.debug('prepared zip file for group %(group)s of camera %(id)s with key %(key)s' % {
                            'group': group, 'id': camera_id, 'key': key})
                    self.finish_json({'key': key})
    
                mediafiles.get_zipped_content(camera_config, media_type='picture', callback=on_zip, group=group)
    
            else: # remote camera
                def on_response(response=None, error=None):
                    if error:
                        return self.finish_json({'error': 'Failed to download zip file from %(url)s: %(msg)s.' % {
                                'url': remote.make_camera_url(camera_config), 'msg': error}})
     
                    key = mediafiles.set_prepared_cache(response)
                    logging.debug('prepared zip file for group %(group)s of camera %(id)s with key %(key)s' % {
                            'group': group, 'id': camera_id, 'key': key})
                    self.finish_json({'key': key})

                remote.get_zipped_content(camera_config, media_type='picture', callback=on_response, group=group)

    @BaseHandler.auth()
    def timelapse(self, camera_id, group):
        key = self.get_argument('key', None)
        if key:
            logging.debug('serving timelapse movie for group %(group)s of camera %(id)s with key %(key)s' % {
                    'group': group, 'id': camera_id, 'key': key})
            
            data = mediafiles.get_prepared_cache(key)
            if not data:
                logging.error('prepared cache data for key "%s" does not exist' % key)
                
                raise HTTPError(404, 'no such key')

            camera_config = config.get_camera(camera_id)
            if utils.local_camera(camera_config):
                pretty_filename = camera_config['@name'] + '_' + group
                pretty_filename = re.sub('[^a-zA-Z0-9]', '_', pretty_filename)

            else: # remote camera
                pretty_filename = re.sub('[^a-zA-Z0-9]', '_', group)

            self.set_header('Content-Type', 'video/x-msvideo')
            self.set_header('Content-Disposition', 'attachment; filename=' + pretty_filename + '.avi;')
            self.finish(data)

        else:
            interval = int(self.get_argument('interval'))
            framerate = int(self.get_argument('framerate'))

            logging.debug('preparing timelapse movie for group %(group)s of camera %(id)s with rate %(framerate)s/%(int)s' % {
                    'group': group, 'id': camera_id, 'framerate': framerate, 'int': interval})

            camera_config = config.get_camera(camera_id)
            if utils.local_camera(camera_config):
                def on_timelapse(data):
                    if data is None:
                        return self.finish_json({'error': 'Failed to create timelapse movie file.'})

                    key = mediafiles.set_prepared_cache(data)
                    logging.debug('prepared timelapse movie for group %(group)s of camera %(id)s with key %(key)s' % {
                            'group': group, 'id': camera_id, 'key': key})
                    self.finish_json({'key': key})

                mediafiles.get_timelapse_movie(camera_config, framerate, interval, callback=on_timelapse, group=group)

            else: # remote camera
                def on_response(response=None, error=None):
                    if error:
                        return self.finish_json({'error': 'Failed to download timelapse movie from %(url)s: %(msg)s.' % {
                                'url': remote.make_camera_url(camera_config), 'msg': error}})

                    key = mediafiles.set_prepared_cache(response)
                    logging.debug('prepared timelapse movie for group %(group)s of camera %(id)s with key %(key)s' % {
                            'group': group, 'id': camera_id, 'key': key})
                    self.finish_json({'key': key})
    
                remote.get_timelapse_movie(camera_config, framerate, interval, callback=on_response, group=group)

    def try_finish(self, content):
        try:
            self.finish(content)
            
        except IOError as e:
            logging.warning('could not write response: %(msg)s' % {'msg': unicode(e)})


class MovieHandler(BaseHandler):
    @asynchronous
    def get(self, camera_id, op, filename=None):
        if camera_id is not None:
            camera_id = int(camera_id)
            if camera_id not in config.get_camera_ids():
                raise HTTPError(404, 'no such camera')
        
        if op == 'list':
            self.list(camera_id)
            
        elif op == 'download':
            self.download(camera_id, filename)
        
        elif op == 'preview':
            self.preview(camera_id, filename)
        
        else:
            raise HTTPError(400, 'unknown operation')
    
    @asynchronous
    def post(self, camera_id, op, filename=None):
        if camera_id is not None:
            camera_id = int(camera_id)
            if camera_id not in config.get_camera_ids():
                raise HTTPError(404, 'no such camera')
        
        if op == 'delete':
            self.delete(camera_id, filename)
        
        else:
            raise HTTPError(400, 'unknown operation')
    
    @BaseHandler.auth()
    def list(self, camera_id):
        logging.debug('listing movies for camera %(id)s' % {'id': camera_id})
        
        camera_config = config.get_camera(camera_id)
        if utils.local_camera(camera_config):
            def on_media_list(media_list):
                if media_list is None:
                    return self.finish_json({'error': 'Failed to get movies list.'})

                self.finish_json({
                    'mediaList': media_list,
                    'cameraName': camera_config['@name']
                })
            
            mediafiles.list_media(camera_config, media_type='movie',
                    callback=on_media_list, prefix=self.get_argument('prefix', None))
        
        else:
            def on_response(remote_list=None, error=None):
                if error:
                    return self.finish_json({'error': 'Failed to get movie list for %(url)s: %(msg)s.' % {
                            'url': remote.make_camera_url(camera_config), 'msg': error}})

                self.finish_json(remote_list)
            
            remote.list_media(camera_config, on_response, media_type='movie', prefix=self.get_argument('prefix', None))
    
    @BaseHandler.auth()
    def download(self, camera_id, filename):
        logging.debug('downloading movie %(filename)s of camera %(id)s' % {
                'filename': filename, 'id': camera_id})
        
        camera_config = config.get_camera(camera_id)
        if utils.local_camera(camera_config):
            content = mediafiles.get_media_content(camera_config, filename, 'movie')
            
            pretty_filename = camera_config['@name'] + '_' + os.path.basename(filename)
            self.set_header('Content-Type', 'video/mpeg')
            self.set_header('Content-Disposition', 'attachment; filename=' + pretty_filename + ';')
            
            self.finish(content)
        
        else:
            def on_response(response=None, error=None):
                if error:
                    return self.finish_json({'error': 'Failed to download movie from %(url)s: %(msg)s.' % {
                            'url': remote.make_camera_url(camera_config), 'msg': error}})

                pretty_filename = os.path.basename(filename) # no camera name available w/o additional request
                self.set_header('Content-Type', 'video/mpeg')
                self.set_header('Content-Disposition', 'attachment; filename=' + pretty_filename + ';')
                
                self.finish(response)

            remote.get_media_content(camera_config, on_response, filename=filename, media_type='movie')

    @BaseHandler.auth()
    def preview(self, camera_id, filename):
        logging.debug('previewing movie %(filename)s of camera %(id)s' % {
                'filename': filename, 'id': camera_id})
        
        camera_config = config.get_camera(camera_id)
        if utils.local_camera(camera_config):
            content = mediafiles.get_media_preview(camera_config, filename, 'movie',
                    width=self.get_argument('width', None),
                    height=self.get_argument('height', None))
            
            if content:
                self.set_header('Content-Type', 'image/jpeg')
                
            else:
                self.set_header('Content-Type', 'image/svg+xml')
                content = open(os.path.join(settings.STATIC_PATH, 'img', 'no-preview.svg')).read()
            
            self.finish(content)
        
        else:
            def on_response(content=None, error=None):
                if content:
                    self.set_header('Content-Type', 'image/jpeg')
                    
                else:
                    self.set_header('Content-Type', 'image/svg+xml')
                    content = open(os.path.join(settings.STATIC_PATH, 'img', 'no-preview.svg')).read()

                self.finish(content)
            
            remote.get_media_preview(camera_config, on_response, filename=filename, media_type='movie',
                    width=self.get_argument('width', None),
                    height=self.get_argument('height', None))

    def delete(self, camera_id, filename):
        logging.debug('deleting movie %(filename)s of camera %(id)s' % {
                'filename': filename, 'id': camera_id})
        
        camera_config = config.get_camera(camera_id)
        if utils.local_camera(camera_config):
            try:
                mediafiles.del_media_content(camera_config, filename, 'movie')
                self.finish_json()
                
            except Exception as e:
                self.finish_json({'error': unicode(e)})

        else: # remote camera
            def on_response(response=None, error=None):
                if error:
                    return self.finish_json({'error': 'Failed to delete movie from %(url)s: %(msg)s.' % {
                            'url': remote.make_camera_url(camera_config), 'msg': error}})

                self.finish_json()

            remote.del_media_content(camera_config, on_response, filename=filename, media_type='movie')


class UpdateHandler(BaseHandler):
    @BaseHandler.auth(admin=True)
    def get(self):
        logging.debug('listing versions')
        
        versions = update.get_all_versions()
        current_version = update.get_version()
        update_version = None
        if versions and update.compare_versions(versions[-1], current_version) > 0:
            update_version = versions[-1]

        self.finish_json({
            'update_version': update_version,
            'current_version': current_version
        })

    @BaseHandler.auth(admin=True)
    def post(self):
        version = self.get_argument('version')
        
        logging.debug('performing update to version %(version)s' % {'version': version})
        
        result = update.perform_update(version)
        
        self.finish_json(result)


class PowerHandler(BaseHandler):
    @BaseHandler.auth(admin=True)
    def post(self, op):
        if op == 'shutdown':
            self.shut_down()
    
    def shut_down(self):
        IOLoop.instance().add_timeout(datetime.timedelta(seconds=2), powerctl.shut_down)


class VersionHandler(BaseHandler):
    def get(self):
        self.render('version.html',
                version=update.get_version(),
                hostname=socket.gethostname())
