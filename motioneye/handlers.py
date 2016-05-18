
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

import datetime
import json
import logging
import os
import re
import socket
import subprocess

from tornado.ioloop import IOLoop
from tornado.web import RequestHandler, HTTPError, asynchronous

import config
import mediafiles
import mjpgclient
import motionctl
import powerctl
import prefs
import remote
import settings
import smbctl
import tasks
import template
import update
import uploadservices
import utils
import v4l2ctl


class BaseHandler(RequestHandler):
    def get_all_arguments(self):
        keys = self.request.arguments.keys()
        arguments = dict([(key, self.get_argument(key)) for key in keys])

        for key in self.request.files:
            files = self.request.files[key]
            if len(files) > 1:
                arguments[key] = files

            elif len(files) > 0:
                arguments[key] = files[0]

            else:
                continue
        
        # consider the json passed in body as well
        data = self.get_json()
        if data and isinstance(data, dict):
            arguments.update(data)

        return arguments
    
    def get_json(self):
        if not hasattr(self, '_json'):
            self._json = None
            if self.request.headers.get('Content-Type', '').startswith('application/json'):
                self._json = json.loads(self.request.body)

        return self._json
    
    def get_argument(self, name, default=None):
        DEF = {}
        argument = RequestHandler.get_argument(self, name, default=DEF)
        if argument is DEF:
            # try to find it in json body
            data = self.get_json()
            if data:
                argument = data.get(name, DEF)
        
            if argument is DEF:
                argument = default
        
        return argument
    
    def finish(self, chunk=None):
        import motioneye

        self.set_header('Server', 'motionEye/%s' % motioneye.VERSION)
        RequestHandler.finish(self, chunk=chunk)

    def render(self, template_name, content_type='text/html', **context):
        self.set_header('Content-Type', content_type)
        
        content = template.render(template_name, **context)
        self.finish(content)
    
    def finish_json(self, data={}):
        self.set_header('Content-Type', 'application/json')
        self.finish(json.dumps(data))

    def get_current_user(self):
        main_config = config.get_main()
        
        username = self.get_argument('_username', None)
        signature = self.get_argument('_signature', None)
        login = self.get_argument('_login', None) == 'true'
        if (username == main_config.get('@admin_username') and
            signature == utils.compute_signature(self.request.method, self.request.uri, self.request.body, main_config.get('@admin_password'))):
            
            return 'admin'
        
        elif not username and not main_config.get('@normal_password'): # no authentication required for normal user
            return 'normal'
        
        elif (username == main_config.get('@normal_username') and
            signature == utils.compute_signature(self.request.method, self.request.uri, self.request.body, main_config.get('@normal_password'))):
            
            return 'normal'

        elif username and username != '_' and login:
            logging.error('authentication failed for user %(user)s' % {'user': username})

        return None
    
    def get_pref(self, key):
        return prefs.get(self.current_user or 'anonymous', key)
        
    def set_pref(self, key, value):
        return prefs.set(self.current_user or 'anonymous', key, value)
        
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
                _admin = self.get_argument('_admin', None) == 'true'
                
                user = self.current_user
                if (user is None) or (user != 'admin' and (admin or _admin)):
                    self.set_header('Content-Type', 'application/json')

                    return self.finish_json({'error': 'unauthorized', 'prompt': prompt})

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
    def get(self):
        import motioneye
        
        # additional config
        main_sections = config.get_additional_structure(camera=False, separators=True)[0]
        camera_sections = config.get_additional_structure(camera=True, separators=True)[0]

        self.render('main.html',
                frame=False,
                version=motioneye.VERSION,
                enable_update=settings.ENABLE_UPDATE,
                enable_reboot=settings.ENABLE_REBOOT,
                add_remove_cameras=settings.ADD_REMOVE_CAMERAS,
                main_sections=main_sections,
                camera_sections=camera_sections,
                hostname=socket.gethostname(),
                title=self.get_argument('title', None),
                admin_username=config.get_main().get('@admin_username'),
                old_motion=config.is_old_motion(),
                has_motion=bool(motionctl.find_motion()))
    
    def head(self):
        self.finish()


class ConfigHandler(BaseHandler):
    @asynchronous
    def get(self, camera_id=None, op=None):
        if camera_id is not None:
            camera_id = int(camera_id)
        
        if op == 'get':
            self.get_config(camera_id)
            
        elif op == 'list':
            self.list()
        
        elif op == 'backup':
            self.backup()
            
        elif op == 'authorize':
            self.authorize(camera_id)

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
            
        elif op == 'restore':
            self.restore()
        
        elif op == 'test':
            self.test(camera_id)
            
        else:
            raise HTTPError(400, 'unknown operation')
    
    @BaseHandler.auth(admin=True)
    def get_config(self, camera_id):
        if camera_id:
            logging.debug('getting config for camera %(id)s' % {'id': camera_id})
            
            if camera_id not in config.get_camera_ids():
                raise HTTPError(404, 'no such camera')
            
            local_config = config.get_camera(camera_id)
            if utils.local_motion_camera(local_config):
                ui_config = config.motion_camera_dict_to_ui(local_config)
                    
                self.finish_json(ui_config)
            
            elif utils.remote_camera(local_config):
                def on_response(remote_ui_config=None, error=None):
                    if error:
                        return self.finish_json({'error': 'Failed to get remote camera configuration for %(url)s: %(msg)s.' % {
                                'url': remote.pretty_camera_url(local_config), 'msg': error}})
                    
                    for key, value in local_config.items():
                        remote_ui_config[key.replace('@', '')] = value
                    
                    # replace the real device url with the remote camera path
                    remote_ui_config['device_url'] = remote.pretty_camera_url(local_config)
                    self.finish_json(remote_ui_config)
                
                remote.get_config(local_config, on_response)
                
            else: # assuming simple mjpeg camera
                ui_config = config.simple_mjpeg_camera_dict_to_ui(local_config)
                    
                self.finish_json(ui_config)
            
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
            if utils.local_motion_camera(local_config):
                local_config = config.motion_camera_ui_to_dict(ui_config, local_config)

                config.set_camera(camera_id, local_config)
            
                on_finish(None, True) # (no error, motion needs restart)

            elif utils.remote_camera(local_config):
                # update the camera locally
                local_config['@enabled'] = ui_config['enabled']
                config.set_camera(camera_id, local_config)
                
                if ui_config.has_key('name'):
                    def on_finish_wrapper(error=None):
                        return on_finish(error, False)
                    
                    ui_config['enabled'] = True # never disable the camera remotely 
                    remote.set_config(local_config, ui_config, on_finish_wrapper)
                
                else:
                    # when the ui config supplied has only the enabled state
                    # and no useful fields (such as "name"),
                    # the camera was probably disabled due to errors
                    on_finish(None, False)
                    
            else: # assuming simple mjpeg camera
                local_config = config.simple_mjpeg_camera_ui_to_dict(ui_config, local_config)

                config.set_camera(camera_id, local_config)
            
                on_finish(None, False) # (no error, motion doesn't need restart)

        def set_main_config(ui_config):
            logging.debug('setting main config...')
            
            old_main_config = config.get_main()
            old_admin_credentials = '%s:%s' % (old_main_config.get('@admin_username', ''), old_main_config.get('@admin_password', ''))
            old_normal_credentials = '%s:%s' % (old_main_config.get('@normal_username', ''), old_main_config.get('@normal_password', ''))

            main_config = config.main_ui_to_dict(ui_config)
            main_config.setdefault('thread', old_main_config.get('thread', [])) 
            admin_credentials = '%s:%s' % (main_config.get('@admin_username', ''), main_config.get('@admin_password', ''))
            normal_credentials = '%s:%s' % (main_config.get('@normal_username', ''), main_config.get('@normal_password', ''))

            additional_configs = config.get_additional_structure(camera=False)[1]           
            reboot_config_names = [('@_' + c['name']) for c in additional_configs.values() if c.get('reboot')]
            reboot_config_names.append('@admin_password')
            reboot = bool([k for k in reboot_config_names if old_main_config.get(k) != main_config.get(k)])

            config.set_main(main_config)
            
            reload = False
            restart = False
            
            if admin_credentials != old_admin_credentials:
                logging.debug('admin credentials changed, reload needed')
                
                reload = True

            if normal_credentials != old_normal_credentials:
                logging.debug('surveillance credentials changed, all camera configs must be updated')
                
                # reconfigure all local cameras to update the stream authentication options
                for camera_id in config.get_camera_ids():
                    local_config = config.get_camera(camera_id)
                    if not utils.local_motion_camera(local_config):
                        continue
                    
                    ui_config = config.motion_camera_dict_to_ui(local_config)
                    local_config = config.motion_camera_ui_to_dict(ui_config, local_config)

                    config.set_camera(camera_id, local_config)
                    
                    restart = True

            if reboot and settings.ENABLE_REBOOT:
                logging.debug('system settings changed, reboot needed')
        
            else: 
                reboot = False

            return {'reload': reload, 'reboot': reboot, 'restart': restart}
        
        reload = False # indicates that browser should reload the page
        reboot = [False] # indicates that the server will reboot immediately
        restart = [False]  # indicates that the local motion instance was modified and needs to be restarted
        error = [None]
        
        def finish():
            if reboot[0]:
                if settings.ENABLE_REBOOT:
                    def call_reboot():
                        powerctl.reboot()
                    
                    io_loop = IOLoop.instance()
                    io_loop.add_timeout(datetime.timedelta(seconds=2), call_reboot)
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

                # make sure main config is handled first
                items = ui_config.items()
                items.sort(key=lambda (key, cfg): key != 'main')

                for key, cfg in items:
                    if key == 'main':
                        result = set_main_config(cfg)
                        reload = result['reload'] or reload
                        reboot[0] = result['reboot'] or reboot[0]
                        restart[0] = result['restart'] or restart[0]
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
            restart[0] = result['restart']

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
        
        else: # not supported
            self.finish_json({'error': True})

    @BaseHandler.auth()
    def list(self):
        logging.debug('listing cameras')

        proto = self.get_argument('proto')        
        if proto == 'motioneye':  # remote listing
            def on_response(cameras=None, error=None):
                if error:
                    self.finish_json({'error': error})
                    
                else:
                    self.finish_json({'cameras': cameras})

            remote.list(self.get_all_arguments(), on_response)
        
        elif proto == 'netcam':
            scheme = self.get_argument('scheme', 'http')

            def on_response(cameras=None, error=None):
                if error:
                    self.finish_json({'error': error})
                    
                else:
                    self.finish_json({'cameras': cameras})
            
            if scheme in ['http', 'https']:
                utils.test_mjpeg_url(self.get_all_arguments(), auth_modes=['basic'], allow_jpeg=True, callback=on_response)
                
            elif config.motion_rtsp_support() and scheme == 'rtsp':
                utils.test_rtsp_url(self.get_all_arguments(), callback=on_response)
                
            else:
                on_response(error='protocol %s not supported' % scheme)

        elif proto == 'mjpeg':
            def on_response(cameras=None, error=None):
                if error:
                    self.finish_json({'error': error})
                    
                else:
                    self.finish_json({'cameras': cameras})
            
            utils.test_mjpeg_url(self.get_all_arguments(), auth_modes=['basic', 'digest'], allow_jpeg=False, callback=on_response)
        
        elif proto == 'v4l2':
            configured_devices = set()
            for camera_id in config.get_camera_ids():
                data = config.get_camera(camera_id)
                if utils.v4l2_camera(data):
                    configured_devices.add(data['videodevice'])

            cameras = [{'id': d[1], 'name': d[2]} for d in v4l2ctl.list_devices()
                    if (d[0] not in configured_devices) and (d[1] not in configured_devices)]
            
            self.finish_json({'cameras': cameras})

        else:  # assuming local motionEye camera listing
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
                            'name': '&lt;' + remote.pretty_camera_url(local_config) + '&gt;',
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
                
                if utils.local_motion_camera(local_config):
                    ui_config = config.motion_camera_dict_to_ui(local_config)
                    cameras.append(ui_config)
                    check_finished()

                elif utils.remote_camera(local_config):
                    if local_config.get('@enabled') or self.get_argument('force', None) == 'true':
                        remote.get_config(local_config, on_response_builder(camera_id, local_config))
                    
                    else: # don't try to reach the remote of the camera is disabled
                        on_response_builder(camera_id, local_config)(error=True)
                        
                else: # assuming simple mjpeg camera
                    ui_config = config.simple_mjpeg_camera_dict_to_ui(local_config)
                    cameras.append(ui_config)
                    check_finished()
            
            if length[0] == 0:        
                self.finish_json({'cameras': []})

    @BaseHandler.auth(admin=True)
    def add_camera(self):
        logging.debug('adding new camera')
        
        try:
            device_details = json.loads(self.request.body)
            
        except Exception as e:
            logging.error('could not decode json: %(msg)s' % {'msg': unicode(e)})
            
            raise

        camera_config = config.add_camera(device_details)

        if utils.local_motion_camera(camera_config):
            motionctl.stop()
            
            if settings.SMB_SHARES:
                stop, start = smbctl.update_mounts()  # @UnusedVariable

                if start:
                    motionctl.start()
            
            else:
                motionctl.start()
            
            ui_config = config.motion_camera_dict_to_ui(camera_config)
            
            self.finish_json(ui_config)
        
        elif utils.remote_camera(camera_config):
            def on_response(remote_ui_config=None, error=None):
                if error:
                    return self.finish_json({'error': error})

                for key, value in camera_config.items():
                    remote_ui_config[key.replace('@', '')] = value
                
                self.finish_json(remote_ui_config)
                
            remote.get_config(camera_config, on_response)
        
        else: # assuming simple mjpeg camera
            ui_config = config.simple_mjpeg_camera_dict_to_ui(camera_config)
            
            self.finish_json(ui_config)
    
    @BaseHandler.auth(admin=True)
    def rem_camera(self, camera_id):
        logging.debug('removing camera %(id)s' % {'id': camera_id})
        
        local = utils.local_motion_camera(config.get_camera(camera_id))
        config.rem_camera(camera_id)
        
        if local:
            motionctl.stop()
            motionctl.start()
            
        self.finish_json()
        
    @BaseHandler.auth(admin=True)
    def backup(self):
        content = config.backup()
        
        if not content:
            raise Exception('failed to create backup file')

        filename = 'motioneye-config.tar.gz'
        self.set_header('Content-Type', 'application/x-compressed')
        self.set_header('Content-Disposition', 'attachment; filename=' + filename + ';')

        self.finish(content)

    @BaseHandler.auth(admin=True)
    def restore(self):
        try:
            content = self.request.files['files'][0]['body']
            
        except KeyError:
            raise HTTPError(400, 'file attachment required')

        result = config.restore(content)
        if result:
            self.finish_json({'ok': True, 'reboot': result['reboot']})
            
        else:
            self.finish_json({'ok': False})
    
    @BaseHandler.auth(admin=True)
    def test(self, camera_id):
        what = self.get_argument('what')
        data = self.get_all_arguments()
        camera_config = config.get_camera(camera_id)
        if what == 'upload_service':
            service_name = data.get('service')
            if not service_name:
                raise HTTPError(400, 'service_name required')

            if utils.local_motion_camera(camera_config): 
                service = uploadservices.get(camera_id, service_name)
                service.load(data)
                if not service:
                    raise HTTPError(400, 'unknown upload service %s' % service_name)
                
                logging.debug('testing access to %s' % service)
                result = service.test_access()
                if result is True:
                    logging.debug('accessing %s succeeded' % service)
                    self.finish_json()
    
                else:
                    logging.warn('accessing %s failed: %s' % (service, result))
                    self.finish_json({'error': result})
            
            elif utils.remote_camera(camera_config):
                def on_response(result=None, error=None):
                    if result is True:
                        self.finish_json()
                        
                    else:
                        result = result or error
                        self.finish_json({'error': result})

                remote.test(camera_config, data, on_response)

        else:
            raise HTTPError(400, 'unknown test %s' % what)

    @BaseHandler.auth(admin=True)
    def authorize(self, camera_id):
        service_name = self.get_argument('service')
        if not service_name:
            raise HTTPError(400, 'service_name required')

        service = uploadservices.get(camera_id, service_name)
        if not service:
            raise HTTPError(400, 'unknown upload service %s' % service_name)

        url = service.get_authorize_url()

        logging.debug('redirected to authorization url %s' % url)
        self.redirect(url)


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
        if group == '/': # ungrouped
            group = ''
        
        if camera_id is not None:
            camera_id = int(camera_id)
            if camera_id not in config.get_camera_ids():
                raise HTTPError(404, 'no such camera')
        
        if op == 'delete':
            self.delete(camera_id, filename)

        elif op == 'delete_all':
            self.delete_all(camera_id, group)
        
        else:
            raise HTTPError(400, 'unknown operation')
    
    @BaseHandler.auth(prompt=False)
    def current(self, camera_id):
        self.set_header('Content-Type', 'image/jpeg')
        
        width = self.get_argument('width', None)
        height = self.get_argument('height', None)
        
        width = width and float(width)
        height = height and float(height)
        
        camera_config = config.get_camera(camera_id)
        if utils.local_motion_camera(camera_config):
            picture = mediafiles.get_current_picture(camera_config,
                    width=width,
                    height=height)
            
            self.set_cookie('motion_detected_' + str(camera_id), str(motionctl.is_motion_detected(camera_id)).lower())
            self.set_cookie('capture_fps_' + str(camera_id), '%.1f' % mjpgclient.get_fps(camera_id))
            self.try_finish(picture)

        elif utils.remote_camera(camera_config):
            def on_response(motion_detected=False, fps=None, picture=None, error=None):
                if error:
                    return self.try_finish(None)

                self.set_cookie('motion_detected_' + str(camera_id), str(motion_detected).lower())
                self.set_cookie('capture_fps_' + str(camera_id), '%.1f' % fps)
                self.try_finish(picture)
            
            remote.get_current_picture(camera_config, width=width, height=height, callback=on_response)
            
        else: # assuming simple mjpeg camera
            raise HTTPError(400, 'unknown operation')
            

    @BaseHandler.auth()
    def list(self, camera_id):
        logging.debug('listing pictures for camera %(id)s' % {'id': camera_id})
        
        camera_config = config.get_camera(camera_id)
        if utils.local_motion_camera(camera_config):
            def on_media_list(media_list):
                if media_list is None:
                    return self.finish_json({'error': 'Failed to get pictures list.'})

                self.finish_json({
                    'mediaList': media_list,
                    'cameraName': camera_config['@name']
                })
            
            mediafiles.list_media(camera_config, media_type='picture',
                    callback=on_media_list, prefix=self.get_argument('prefix', None))

        elif utils.remote_camera(camera_config):
            def on_response(remote_list=None, error=None):
                if error:
                    return self.finish_json({'error': 'Failed to get picture list for %(url)s: %(msg)s.' % {
                            'url': remote.pretty_camera_url(camera_config), 'msg': error}})

                self.finish_json(remote_list)
            
            remote.list_media(camera_config, media_type='picture', prefix=self.get_argument('prefix', None), callback=on_response)

        else: # assuming simple mjpeg camera
            raise HTTPError(400, 'unknown operation')

    def frame(self, camera_id):
        camera_config = config.get_camera(camera_id)
        
        if utils.local_motion_camera(camera_config) or utils.simple_mjpeg_camera(camera_config) or self.get_argument('title', None) is not None:
            self.render('main.html',
                    frame=True,
                    camera_id=camera_id,
                    camera_config=camera_config,
                    title=self.get_argument('title', camera_config.get('@name', '')),
                    admin_username=config.get_main().get('@admin_username'))

        elif utils.remote_camera(camera_config):
            def on_response(remote_ui_config=None, error=None):
                if error:
                    return self.render('main.html',
                            frame=True,
                            camera_id=camera_id,
                            camera_config=camera_config,
                            title=self.get_argument('title', ''))

                # issue a fake motion_camera_ui_to_dict() call to transform
                # the remote UI values into motion config directives
                remote_config = config.motion_camera_ui_to_dict(remote_ui_config)
                
                self.render('main.html',
                        frame=True,
                        camera_id=camera_id,
                        camera_config=remote_config,
                        title=self.get_argument('title', remote_config['@name']),
                        admin_username=config.get_main().get('@admin_username'))

            remote.get_config(camera_config, on_response)
        
    @BaseHandler.auth()
    def download(self, camera_id, filename):
        logging.debug('downloading picture %(filename)s of camera %(id)s' % {
                'filename': filename, 'id': camera_id})
        
        camera_config = config.get_camera(camera_id)
        if utils.local_motion_camera(camera_config):
            content = mediafiles.get_media_content(camera_config, filename, 'picture')
            
            pretty_filename = camera_config['@name'] + '_' + os.path.basename(filename)
            self.set_header('Content-Type', 'image/jpeg')
            self.set_header('Content-Disposition', 'attachment; filename=' + pretty_filename + ';')
            
            self.finish(content)
        
        elif utils.remote_camera(camera_config):
            def on_response(response=None, error=None):
                if error:
                    return self.finish_json({'error': 'Failed to download picture from %(url)s: %(msg)s.' % {
                            'url': remote.pretty_camera_url(camera_config), 'msg': error}})

                pretty_filename = os.path.basename(filename) # no camera name available w/o additional request
                self.set_header('Content-Type', 'image/jpeg')
                self.set_header('Content-Disposition', 'attachment; filename=' + pretty_filename + ';')
                
                self.finish(response)

            remote.get_media_content(camera_config, filename=filename, media_type='picture', callback=on_response)

        else: # assuming simple mjpeg camera
            raise HTTPError(400, 'unknown operation')

    @BaseHandler.auth()
    def preview(self, camera_id, filename):
        logging.debug('previewing picture %(filename)s of camera %(id)s' % {
                'filename': filename, 'id': camera_id})
        
        camera_config = config.get_camera(camera_id)
        if utils.local_motion_camera(camera_config):
            content = mediafiles.get_media_preview(camera_config, filename, 'picture',
                    width=self.get_argument('width', None),
                    height=self.get_argument('height', None))
            
            if content:
                self.set_header('Content-Type', 'image/jpeg')
                
            else:
                self.set_header('Content-Type', 'image/svg+xml')
                content = open(os.path.join(settings.STATIC_PATH, 'img', 'no-preview.svg')).read()
                
            self.finish(content)
        
        elif utils.remote_camera(camera_config):
            def on_response(content=None, error=None):
                if content:
                    self.set_header('Content-Type', 'image/jpeg')
                    
                else:
                    self.set_header('Content-Type', 'image/svg+xml')
                    content = open(os.path.join(settings.STATIC_PATH, 'img', 'no-preview.svg')).read()
                
                self.finish(content)
            
            remote.get_media_preview(camera_config, filename=filename, media_type='picture',
                    width=self.get_argument('width', None),
                    height=self.get_argument('height', None),
                    callback=on_response)

        else: # assuming simple mjpeg camera
            raise HTTPError(400, 'unknown operation')
    
    @BaseHandler.auth(admin=True)
    def delete(self, camera_id, filename):
        logging.debug('deleting picture %(filename)s of camera %(id)s' % {
                'filename': filename, 'id': camera_id})
        
        camera_config = config.get_camera(camera_id)
        if utils.local_motion_camera(camera_config):
            try:
                mediafiles.del_media_content(camera_config, filename, 'picture')
                self.finish_json()
                
            except Exception as e:
                self.finish_json({'error': unicode(e)})

        elif utils.remote_camera(camera_config):
            def on_response(response=None, error=None):
                if error:
                    return self.finish_json({'error': 'Failed to delete picture from %(url)s: %(msg)s.' % {
                            'url': remote.pretty_camera_url(camera_config), 'msg': error}})

                self.finish_json()

            remote.del_media_content(camera_config, filename=filename, media_type='picture', callback=on_response)

        else: # assuming simple mjpeg camera
            raise HTTPError(400, 'unknown operation')

    @BaseHandler.auth()
    def zipped(self, camera_id, group):
        key = self.get_argument('key', None)
        camera_config = config.get_camera(camera_id)
        
        if key:
            logging.debug('serving zip file for group "%(group)s" of camera %(id)s with key %(key)s' % {
                    'group': group or 'ungrouped', 'id': camera_id, 'key': key})
            
            if utils.local_motion_camera(camera_config):
                data = mediafiles.get_prepared_cache(key)
                if not data:
                    logging.error('prepared cache data for key "%s" does not exist' % key)
                    
                    raise HTTPError(404, 'no such key')

                pretty_filename = camera_config['@name'] + '_' + group
                pretty_filename = re.sub('[^a-zA-Z0-9]', '_', pretty_filename)
         
                self.set_header('Content-Type', 'application/zip')
                self.set_header('Content-Disposition', 'attachment; filename=' + pretty_filename + '.zip;')
                self.finish(data)
                
            elif utils.remote_camera(camera_config):
                def on_response(response=None, error=None):
                    if error:
                        return self.finish_json({'error': 'Failed to download zip file from %(url)s: %(msg)s.' % {
                                'url': remote.pretty_camera_url(camera_config), 'msg': error}})

                    self.set_header('Content-Type', response['content_type'])
                    self.set_header('Content-Disposition', response['content_disposition'])
                    self.finish(response['data'])

                remote.get_zipped_content(camera_config, media_type='picture', key=key, group=group, callback=on_response)

            else: # assuming simple mjpeg camera
                raise HTTPError(400, 'unknown operation')

        else: # prepare
            logging.debug('preparing zip file for group "%(group)s" of camera %(id)s' % {
                    'group': group or 'ungrouped', 'id': camera_id})

            if utils.local_motion_camera(camera_config):
                def on_zip(data):
                    if data is None:
                        return self.finish_json({'error': 'Failed to create zip file.'})
    
                    key = mediafiles.set_prepared_cache(data)
                    logging.debug('prepared zip file for group "%(group)s" of camera %(id)s with key %(key)s' % {
                            'group': group or 'ungrouped', 'id': camera_id, 'key': key})
                    self.finish_json({'key': key})
    
                mediafiles.get_zipped_content(camera_config, media_type='picture', group=group, callback=on_zip)
    
            elif utils.remote_camera(camera_config):
                def on_response(response=None, error=None):
                    if error:
                        return self.finish_json({'error': 'Failed to make zip file at %(url)s: %(msg)s.' % {
                                'url': remote.pretty_camera_url(camera_config), 'msg': error}})

                    self.finish_json({'key': response['key']})

                remote.make_zipped_content(camera_config, media_type='picture', group=group, callback=on_response)

            else: # assuming simple mjpeg camera
                raise HTTPError(400, 'unknown operation')

    @BaseHandler.auth()
    def timelapse(self, camera_id, group):
        key = self.get_argument('key', None)
        check = self.get_argument('check', False)
        camera_config = config.get_camera(camera_id)

        if key: # download
            logging.debug('serving timelapse movie for group "%(group)s" of camera %(id)s with key %(key)s' % {
                    'group': group or 'ungrouped', 'id': camera_id, 'key': key})
            
            if utils.local_motion_camera(camera_config):
                data = mediafiles.get_prepared_cache(key)
                if data is None:
                    logging.error('prepared cache data for key "%s" does not exist' % key)

                    raise HTTPError(404, 'no such key')

                pretty_filename = camera_config['@name'] + '_' + group
                pretty_filename = re.sub('[^a-zA-Z0-9]', '_', pretty_filename)
    
                self.set_header('Content-Type', 'video/x-msvideo')
                self.set_header('Content-Disposition', 'attachment; filename=' + pretty_filename + '.avi;')
                self.finish(data)

            elif utils.remote_camera(camera_config):
                def on_response(response=None, error=None):
                    if error:
                        return self.finish_json({'error': 'Failed to download timelapse movie from %(url)s: %(msg)s.' % {
                                'url': remote.pretty_camera_url(camera_config), 'msg': error}})

                    self.set_header('Content-Type', response['content_type'])
                    self.set_header('Content-Disposition', response['content_disposition'])
                    self.finish(response['data'])

                remote.get_timelapse_movie(camera_config, key, group=group, callback=on_response)

            else: # assuming simple mjpeg camera
                raise HTTPError(400, 'unknown operation')

        elif check:
            logging.debug('checking timelapse movie status for group "%(group)s" of camera %(id)s' % {
                    'group': group or 'ungrouped', 'id': camera_id})

            if utils.local_motion_camera(camera_config):
                status = mediafiles.check_timelapse_movie()
                if status['progress'] == -1 and status['data']:
                    key = mediafiles.set_prepared_cache(status['data'])
                    logging.debug('prepared timelapse movie for group "%(group)s" of camera %(id)s with key %(key)s' % {
                            'group': group or 'ungrouped', 'id': camera_id, 'key': key})
                    self.finish_json({'key': key, 'progress': -1})

                else:
                    self.finish_json(status)

            elif utils.remote_camera(camera_config):
                def on_response(response=None, error=None):
                    if error:
                        return self.finish_json({'error': 'Failed to check timelapse movie progress at %(url)s: %(msg)s.' % {
                                'url': remote.pretty_camera_url(camera_config), 'msg': error}})

                    if response['progress'] == -1 and response.get('key'):
                        self.finish_json({'key': response['key'], 'progress': -1})
                    
                    else:
                        self.finish_json(response)

                remote.check_timelapse_movie(camera_config, group=group, callback=on_response)

            else: # assuming simple mjpeg camera
                raise HTTPError(400, 'unknown operation')

        else: # start timelapse
            interval = int(self.get_argument('interval'))
            framerate = int(self.get_argument('framerate'))

            logging.debug('preparing timelapse movie for group "%(group)s" of camera %(id)s with rate %(framerate)s/%(int)s' % {
                    'group': group or 'ungrouped', 'id': camera_id, 'framerate': framerate, 'int': interval})

            if utils.local_motion_camera(camera_config):
                status = mediafiles.check_timelapse_movie()
                if status['progress'] != -1:
                    self.finish_json({'progress': status['progress']}) # timelapse already active

                else:
                    mediafiles.make_timelapse_movie(camera_config, framerate, interval, group=group)
                    self.finish_json({'progress': -1})

            elif utils.remote_camera(camera_config):
                def on_status(response=None, error=None):
                    if error:
                        return self.finish_json({'error': 'Failed to make timelapse movie at %(url)s: %(msg)s.' % {
                                'url': remote.pretty_camera_url(camera_config), 'msg': error}})
                    
                    if response['progress'] != -1:
                        return self.finish_json({'progress': response['progress']}) # timelapse already active
    
                    def on_make(response=None, error=None):
                        if error:
                            return self.finish_json({'error': 'Failed to make timelapse movie at %(url)s: %(msg)s.' % {
                                    'url': remote.pretty_camera_url(camera_config), 'msg': error}})
    
                        self.finish_json({'progress': -1})
                    
                    remote.make_timelapse_movie(camera_config, framerate, interval, group=group, callback=on_make)

                remote.check_timelapse_movie(camera_config, group=group, callback=on_status)

            else: # assuming simple mjpeg camera
                raise HTTPError(400, 'unknown operation')

    @BaseHandler.auth(admin=True)
    def delete_all(self, camera_id, group):
        logging.debug('deleting picture group "%(group)s" of camera %(id)s' % {
                'group': group or 'ungrouped', 'id': camera_id})

        camera_config = config.get_camera(camera_id)
        if utils.local_motion_camera(camera_config):
            try:
                mediafiles.del_media_group(camera_config, group, 'picture')
                self.finish_json()
                
            except Exception as e:
                self.finish_json({'error': unicode(e)})

        elif utils.remote_camera(camera_config):
            def on_response(response=None, error=None):
                if error:
                    return self.finish_json({'error': 'Failed to delete picture group at %(url)s: %(msg)s.' % {
                            'url': remote.pretty_camera_url(camera_config), 'msg': error}})

                self.finish_json()

            remote.del_media_group(camera_config, group=group, media_type='picture', callback=on_response)

        else: # assuming simple mjpeg camera
            raise HTTPError(400, 'unknown operation')

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
    def post(self, camera_id, op, filename=None, group=None):
        if group == '/': # ungrouped
            group = ''

        if camera_id is not None:
            camera_id = int(camera_id)
            if camera_id not in config.get_camera_ids():
                raise HTTPError(404, 'no such camera')
        
        if op == 'delete':
            self.delete(camera_id, filename)
        
        elif op == 'delete_all':
            self.delete_all(camera_id, group)
        
        else:
            raise HTTPError(400, 'unknown operation')
    
    @BaseHandler.auth()
    def list(self, camera_id):
        logging.debug('listing movies for camera %(id)s' % {'id': camera_id})
        
        camera_config = config.get_camera(camera_id)
        if utils.local_motion_camera(camera_config):
            def on_media_list(media_list):
                if media_list is None:
                    return self.finish_json({'error': 'Failed to get movies list.'})

                self.finish_json({
                    'mediaList': media_list,
                    'cameraName': camera_config['@name']
                })
            
            mediafiles.list_media(camera_config, media_type='movie',
                    callback=on_media_list, prefix=self.get_argument('prefix', None))
        
        elif utils.remote_camera(camera_config):
            def on_response(remote_list=None, error=None):
                if error:
                    return self.finish_json({'error': 'Failed to get movie list for %(url)s: %(msg)s.' % {
                            'url': remote.pretty_camera_url(camera_config), 'msg': error}})

                self.finish_json(remote_list)
            
            remote.list_media(camera_config, media_type='movie', prefix=self.get_argument('prefix', None), callback=on_response)

        else: # assuming simple mjpeg camera
            raise HTTPError(400, 'unknown operation')

    @BaseHandler.auth()
    def download(self, camera_id, filename):
        logging.debug('downloading movie %(filename)s of camera %(id)s' % {
                'filename': filename, 'id': camera_id})
        
        camera_config = config.get_camera(camera_id)
        if utils.local_motion_camera(camera_config):
            content = mediafiles.get_media_content(camera_config, filename, 'movie')
            
            pretty_filename = camera_config['@name'] + '_' + os.path.basename(filename)
            self.set_header('Content-Type', 'video/mpeg')
            self.set_header('Content-Disposition', 'attachment; filename=' + pretty_filename + ';')
            
            self.finish(content)
        
        elif utils.remote_camera(camera_config):
            def on_response(response=None, error=None):
                if error:
                    return self.finish_json({'error': 'Failed to download movie from %(url)s: %(msg)s.' % {
                            'url': remote.pretty_camera_url(camera_config), 'msg': error}})

                pretty_filename = os.path.basename(filename) # no camera name available w/o additional request
                self.set_header('Content-Type', 'video/mpeg')
                self.set_header('Content-Disposition', 'attachment; filename=' + pretty_filename + ';')
                
                self.finish(response)

            remote.get_media_content(camera_config, filename=filename, media_type='movie', callback=on_response)

        else: # assuming simple mjpeg camera
            raise HTTPError(400, 'unknown operation')

    @BaseHandler.auth()
    def preview(self, camera_id, filename):
        logging.debug('previewing movie %(filename)s of camera %(id)s' % {
                'filename': filename, 'id': camera_id})
        
        camera_config = config.get_camera(camera_id)
        if utils.local_motion_camera(camera_config):
            content = mediafiles.get_media_preview(camera_config, filename, 'movie',
                    width=self.get_argument('width', None),
                    height=self.get_argument('height', None))
            
            if content:
                self.set_header('Content-Type', 'image/jpeg')
                
            else:
                self.set_header('Content-Type', 'image/svg+xml')
                content = open(os.path.join(settings.STATIC_PATH, 'img', 'no-preview.svg')).read()
            
            self.finish(content)
        
        elif utils.remote_camera(camera_config):
            def on_response(content=None, error=None):
                if content:
                    self.set_header('Content-Type', 'image/jpeg')
                    
                else:
                    self.set_header('Content-Type', 'image/svg+xml')
                    content = open(os.path.join(settings.STATIC_PATH, 'img', 'no-preview.svg')).read()

                self.finish(content)
            
            remote.get_media_preview(camera_config, filename=filename, media_type='movie',
                    width=self.get_argument('width', None),
                    height=self.get_argument('height', None),
                    callback=on_response)

        else: # assuming simple mjpeg camera
            raise HTTPError(400, 'unknown operation')

    @BaseHandler.auth(admin=True)
    def delete(self, camera_id, filename):
        logging.debug('deleting movie %(filename)s of camera %(id)s' % {
                'filename': filename, 'id': camera_id})
        
        camera_config = config.get_camera(camera_id)
        if utils.local_motion_camera(camera_config):
            try:
                mediafiles.del_media_content(camera_config, filename, 'movie')
                self.finish_json()
                
            except Exception as e:
                self.finish_json({'error': unicode(e)})

        elif utils.remote_camera(camera_config):
            def on_response(response=None, error=None):
                if error:
                    return self.finish_json({'error': 'Failed to delete movie from %(url)s: %(msg)s.' % {
                            'url': remote.pretty_camera_url(camera_config), 'msg': error}})

                self.finish_json()

            remote.del_media_content(camera_config, filename=filename, media_type='movie', callback=on_response)

        else: # assuming simple mjpeg camera
            raise HTTPError(400, 'unknown operation')

    @BaseHandler.auth(admin=True)
    def delete_all(self, camera_id, group):
        logging.debug('deleting movie group "%(group)s" of camera %(id)s' % {
                'group': group or 'ungrouped', 'id': camera_id})

        camera_config = config.get_camera(camera_id)
        if utils.local_motion_camera(camera_config):
            try:
                mediafiles.del_media_group(camera_config, group, 'movie')
                self.finish_json()
                
            except Exception as e:
                self.finish_json({'error': unicode(e)})

        elif utils.remote_camera(camera_config):
            def on_response(response=None, error=None):
                if error:
                    return self.finish_json({'error': 'Failed to delete movie group at %(url)s: %(msg)s.' % {
                            'url': remote.pretty_camera_url(camera_config), 'msg': error}})

                self.finish_json()

            remote.del_media_group(camera_config, group=group, media_type='movie', callback=on_response)

        else: # assuming simple mjpeg camera
            raise HTTPError(400, 'unknown operation')


class ActionHandler(BaseHandler):
    @asynchronous
    def post(self, camera_id, action):
        camera_id = int(camera_id)
        if camera_id not in config.get_camera_ids():
            raise HTTPError(404, 'no such camera')
        
        local_config = config.get_camera(camera_id)
        if utils.remote_camera(local_config):
            def on_response(error=None):
                if error:
                    return self.finish_json({'error': 'Failed to execute action on remote camera at %(url)s: %(msg)s.' % {
                            'url': remote.pretty_camera_url(local_config), 'msg': error}})

                self.finish_json()

            return remote.exec_action(local_config, action, on_response)

        if action == 'snapshot':
            logging.debug('executing snapshot action for camera with id %s' % camera_id)
            return self.snapshot()
        
        elif action == 'record_start':
            logging.debug('executing record_start action for camera with id %s' % camera_id)
            return self.record_start()
        
        elif action == 'record_stop':
            logging.debug('executing record_stop action for camera with id %s' % camera_id)
            return self.record_stop()

        action_commands = config.get_action_commands(camera_id)
        command = action_commands.get(action)
        if not command:
            raise HTTPError(400, 'unknown action')

        logging.debug('executing %s action for camera with id %s: "%s"' % (action, camera_id, command))
        self.run_command_bg(command)
    
    def run_command_bg(self, command):
        self.p = subprocess.Popen(command, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
        self.command = command
        
        self.io_loop = IOLoop.instance()
        self.io_loop.add_timeout(datetime.timedelta(milliseconds=100), self.check_command)
    
    def check_command(self):
        exit_status = self.p.poll()
        if exit_status is not None:
            output = self.p.stdout.read()
            lines = output.split('\n')
            if not lines[-1]:
                lines = lines[:-1]
            command = os.path.basename(self.command)
            if exit_status:
                logging.warn('%s: command has finished with non-zero exit status: %s' % (command, exit_status))
                for line in lines:
                    logging.warn('%s: %s' % (command, line))

            else:
                logging.debug('%s: command has finished' % command)
                for line in lines:
                    logging.debug('%s: %s' % (command, line))

            self.finish_json({'status': exit_status})

        else:
            self.io_loop.add_timeout(datetime.timedelta(milliseconds=100), self.check_command)
    
    def snapshot(self):
        self.finish_json({})
    
    def record_start(self):
        self.finish_json({})
    
    def record_stop(self):
        self.finish_json({})


class PrefsHandler(BaseHandler):
    def get(self, key=None):
        self.finish_json(self.get_pref(key))

    def post(self, key=None):
        try:
            value = json.loads(self.request.body)

        except Exception as e:
            logging.error('could not decode json: %s' % e)

            raise

        self.set_pref(key, value)
    

class RelayEventHandler(BaseHandler):
    @BaseHandler.auth(admin=True)
    def post(self):
        event = self.get_argument('event')
        thread_id = int(self.get_argument('thread_id'))

        camera_id = motionctl.thread_id_to_camera_id(thread_id)
        if camera_id is None:
            logging.debug('ignoring event for unknown thread id %s' % thread_id)
            return self.finish_json()

        else:
            logging.debug('recevied relayed event %(event)s for thread id %(id)s (camera id %(cid)s)' % {
                    'event': event, 'id': thread_id, 'cid': camera_id})
        
        camera_config = config.get_camera(camera_id)
        if not utils.local_motion_camera(camera_config):
            logging.warn('ignoring event for non-local camera with id %s' % camera_id)
            return self.finish_json()
        
        if event == 'start':
            if not camera_config['@motion_detection']:
                logging.debug('ignoring start event for camera with id %s and motion detection disabled' % camera_id)
                return self.finish_json()

            motionctl.set_motion_detected(camera_id, True)
            
        elif event == 'stop':
            motionctl.set_motion_detected(camera_id, False)
            
        elif event == 'movie_end':
            filename = self.get_argument('filename')
            
            # generate preview (thumbnail)
            tasks.add(5, mediafiles.make_movie_preview, tag='make_movie_preview(%s)' % filename, async=True,
                    camera_config=camera_config, full_path=filename)

            # upload to external service
            if camera_config['@upload_enabled'] and camera_config['@upload_movie']:
                self.upload_media_file(filename, camera_id, camera_config)

        elif event == 'picture_save':
            filename = self.get_argument('filename')
            
            # upload to external service
            if camera_config['@upload_enabled'] and camera_config['@upload_picture']:
                self.upload_media_file(filename, camera_id, camera_config)

        else:
            logging.warn('unknown event %s' % event)

        self.finish_json()
    
    def upload_media_file(self, filename, camera_id, camera_config):
        service_name = camera_config['@upload_service']

        tasks.add(5, uploadservices.upload_media_file, tag='upload_media_file(%s)' % filename, async=True,
                camera_id=camera_id, service_name=service_name,
                target_dir=camera_config['@upload_subfolders'] and camera_config['target_dir'],
                filename=filename)


class LogHandler(BaseHandler):
    LOGS = {
        'motion': (os.path.join(settings.LOG_PATH, 'motion.log'),  'motion.log'),
    }

    @BaseHandler.auth(admin=True)
    def get(self, name):
        log = self.LOGS.get(name)
        if log is None:
            raise HTTPError(404, 'no such log')

        (path, filename) = log

        self.set_header('Content-Type', 'text/plain')
        self.set_header('Content-Disposition', 'attachment; filename=' + filename + ';')

        if path.startswith('/'): # an actual path        
            logging.debug('serving log file "%s" from "%s"' % (filename, path))

            with open(path) as f:
                self.finish(f.read())
                
        else: # a command to execute 
            logging.debug('serving log file "%s" from command "%s"' % (filename, path))

            try:
                output = subprocess.check_output(path.split())

            except Exception as e:
                output = 'failed to execute command: %s' % e
                
            self.finish(output)
                

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
            
        elif op == 'reboot':
            self.reboot()
    
    def shut_down(self):
        io_loop = IOLoop.instance()
        io_loop.add_timeout(datetime.timedelta(seconds=2), powerctl.shut_down)

    def reboot(self):
        io_loop = IOLoop.instance()
        io_loop.add_timeout(datetime.timedelta(seconds=2), powerctl.reboot)


class VersionHandler(BaseHandler):
    def get(self):
        self.render('version.html',
                version=update.get_version(),
                hostname=socket.gethostname())

    post = get


# this will only trigger the login mechanism on the client side, if required 
class LoginHandler(BaseHandler):
    @BaseHandler.auth()
    def get(self):
        self.finish_json()

    def post(self):
        self.set_header('Content-Type', 'text/html')
        self.finish()
