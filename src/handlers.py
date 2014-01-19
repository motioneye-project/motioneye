
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
import json
import logging
import os
import sys

from tornado.web import RequestHandler, HTTPError, asynchronous

import config
import mediafiles
import motionctl
import remote
import settings
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
    
    def _handle_request_exception(self, e):
        # don't send a traceback to the client
        if isinstance(e, HTTPError):
            if e.log_message:
                format = "%d %s: " + e.log_message
                args = [e.status_code, self._request_summary()] + list(e.args)
                logging.warning(format, *args)
            
            status_code = e.status_code

        else:
            logging.error('Uncaught exception %s\n%r', self._request_summary(), self.request, exc_info=True)
            
            status_code = 500
            
        try:
            self.send_error(status_code, exc_info=sys.exc_info())
        
        except Exception as e:
            logging.warning('could not send error to client: %(msg)s' % {'msg': unicode(e)})
        
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
            
            local_config = config.get_camera(camera_id)
            if local_config['@proto'] != 'v4l2':
                def on_response(remote_ui_config):
                    if remote_ui_config is None:
                        return self.finish_json({'error': 'Failed to get remote camera configuration for %(url)s.' % {
                                'url': utils.make_camera_url(local_config)}})
                    
                    for key, value in local_config.items():
                        remote_ui_config[key.replace('@', '')] = value
                    
                    self.finish_json(remote_ui_config)
                
                remote.get_config(local_config, on_response)
            
            else:
                ui_config = config.camera_dict_to_ui(local_config)
                    
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
            if local_config['@proto'] == 'v4l2':
                # overwrite some fields whose values should not be changed this way
                ui_config['device_uri'] = local_config['videodevice']
                ui_config['proto'] = 'v4l2'
                ui_config['host'] = ''
                ui_config['port'] = ''
                ui_config.setdefault('enabled', True)
                
                local_config = config.camera_ui_to_dict(ui_config)
                config.set_camera(camera_id, local_config)
            
                on_finish(None, True) # (no error, motion needs restart)
        
            else:
                # update the camera locally
                local_config['@enabled'] = ui_config['enabled']
                config.set_camera(camera_id, local_config)
                
                # when the local_config supplied has only the enabled state,
                # the camera was probably disabled due to errors

                if ui_config.has_key('device_uri'):
                    # delete some fields that should not get to the remote side as they are
                    del ui_config['device_uri']
                    del ui_config['proto']
                    del ui_config['host']
                    del ui_config['port']
                    del ui_config['enabled']
                    
                    def on_finish_wrapper(error):
                        return on_finish(error, False)
                    
                    remote.set_config(local_config, ui_config, on_finish_wrapper)

        def set_main_config(ui_config):
            logging.debug('setting main config...')
            
            old_main_config = config.get_main()
            old_admin_credentials = old_main_config.get('@admin_username', '') + ':' + old_main_config.get('@admin_password', '')
            
            main_config = config.main_ui_to_dict(ui_config)
            admin_credentials = main_config.get('@admin_username', '') + ':' + main_config.get('@admin_password', '')
            
            config.set_main(main_config)
            
            if admin_credentials != old_admin_credentials:
                logging.debug('admin credentials changed, reload needed')
                
                return True # needs browser reload
                
            return False
        
        reload = False # indicates that browser should reload the page
        restart = [False]  # indicates that the local motion instance was modified and needs to be restarted
        error = [None]
        
        def finish():
            if restart[0]:
                logging.debug('motion needs to be restarted')
                motionctl.restart()

            self.finish({'reload': reload, 'error': error[0]})
        
        if camera_id is not None:
            if camera_id == 0: # multiple camera configs
                logging.debug('setting multiple configs')
                
                so_far = [0]
                def check_finished(e, r):
                    restart[0] = restart[0] or r
                    error[0] = error[0] or e
                    so_far[0] += 1
                    
                    if so_far[0] >= len(ui_config): # finished
                        finish()
        
                for key, cfg in ui_config.items():
                    if key == 'main':
                        reload = set_main_config(cfg) or reload
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
            reload = set_main_config(ui_config)

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
            
            remote.set_preview(camera_config, controls, on_response)

    @BaseHandler.auth()
    def list_cameras(self):
        logging.debug('listing cameras')
        
        if 'host' in self.get_data():  # remote listing
            def on_response(cameras):
                if cameras is None:
                    self.finish_json({'error': 'Failed to list remote cameras.'})
                    
                else:
                    cameras = [c for c in cameras if c.get('enabled')]
                    self.finish_json({'cameras': cameras})
            
            remote.list_cameras(self.get_data(), on_response)
                
        else:  # local listing
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
                def on_response(remote_ui_config):
                    if remote_ui_config is None:
                        cameras.append({
                            'id': camera_id,
                            'name': '&lt;' + utils.make_camera_url(local_config) + '&gt;',
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
                            
                        cameras.append(remote_ui_config)
                        
                    check_finished()
                    
                return on_response
            
            for camera_id in camera_ids:
                local_config = config.get_camera(camera_id)
                if local_config['@proto'] == 'v4l2':
                    ui_config = config.camera_dict_to_ui(local_config)
                    cameras.append(ui_config)
                    check_finished()

                else:  # remote camera
                    remote.get_config(local_config, on_response_builder(camera_id, local_config))
            
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

        devices = [{'device_uri': d[0], 'name': d[1], 'configured': d[0] in configured_devices}
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
            for (w, h) in v4l2ctl.list_resolutions(device_details['device_uri']):
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
            
            self.finish_json(ui_config)
        
        else:
            def on_response(remote_ui_config):
                if remote_ui_config is None:
                    self.finish_json({'error': True})

                for key, value in camera_config.items():
                    remote_ui_config[key.replace('@', '')] = value
                
                self.finish_json(remote_ui_config)
                
            remote.get_config(device_details, on_response)
    
    @BaseHandler.auth(admin=True)
    def rem_camera(self, camera_id):
        logging.debug('removing camera %(id)s' % {'id': camera_id})
        
        local = config.get_camera(camera_id).get('@proto') == 'v4l2'
        config.rem_camera(camera_id)
        
        if local:
            motionctl.restart()
            
        self.finish_json()


class PictureHandler(BaseHandler):
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
        
        elif op == 'preview':
            self.preview(camera_id, filename)
        
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
        if camera_config['@proto'] == 'v4l2':
            picture = mediafiles.get_current_picture(camera_config,
                    width=width,
                    height=height)
            
            if sequence and picture:
                mediafiles.set_picture_cache(camera_id, sequence, width, picture)

            self.try_finish(picture)
                
        else:
            def on_response(picture):
                if sequence and picture:
                    mediafiles.set_picture_cache(camera_id, sequence, width, picture)
                
                self.try_finish(picture)
            
            remote.get_current_picture(camera_config, on_response, width=width, height=height)

    @BaseHandler.auth()
    def list(self, camera_id):
        logging.debug('listing pictures for camera %(id)s' % {'id': camera_id})
        
        if camera_id not in config.get_camera_ids():
            raise HTTPError(404, 'no such camera')
        
        camera_config = config.get_camera(camera_id)
        if camera_config['@proto'] != 'v4l2':
            def on_response(remote_list):
                if remote_list is None:
                    return self.finish_json({'error': 'Failed to get picture list for %(url)s.' % {
                            'url': utils.make_camera_url(camera_config)}})

                self.finish_json(remote_list)
            
            remote.list_media(camera_config, on_response, media_type='picture', prefix=self.get_argument('prefix', None))
        
        else:
            def on_media_list(media_list):
                if media_list is None:
                    return self.finish_json({'error': 'Failed to get pictures list.'})

                self.finish_json({
                    'mediaList': media_list,
                    'cameraName': camera_config['@name']
                })
            
            mediafiles.list_media(camera_config, media_type='picture',
                    callback=on_media_list, prefix=self.get_argument('prefix', None))

    @BaseHandler.auth()
    def download(self, camera_id, filename):
        logging.debug('downloading picture %(filename)s of camera %(id)s' % {
                'filename': filename, 'id': camera_id})
        
        if camera_id not in config.get_camera_ids():
            raise HTTPError(404, 'no such camera')
        
        camera_config = config.get_camera(camera_id)
        if camera_config['@proto'] != 'v4l2':
            def on_response(response):
                if response is None:
                    return self.finish_json({'error': 'Failed to download picture from %(url)s.' % {
                            'url': utils.make_camera_url(camera_config)}})

                pretty_filename = os.path.basename(filename) # no camera name available w/o additional request
                self.set_header('Content-Type', 'image/jpeg')
                self.set_header('Content-Disposition', 'attachment; filename=' + pretty_filename + ';')
                
                self.finish(response)

            remote.get_media_content(camera_config, on_response, filename=filename, media_type='picture')
            
        else:
            content = mediafiles.get_media_content(camera_config, filename, 'picture')
            
            pretty_filename = camera_config['@name'] + '_' + os.path.basename(filename)
            self.set_header('Content-Type', 'image/jpeg')
            self.set_header('Content-Disposition', 'attachment; filename=' + pretty_filename + ';')
            
            self.finish(content)


    @BaseHandler.auth()
    def preview(self, camera_id, filename):
        logging.debug('previewing picture %(filename)s of camera %(id)s' % {
                'filename': filename, 'id': camera_id})
        
        if camera_id not in config.get_camera_ids():
            raise HTTPError(404, 'no such camera')
        
        camera_config = config.get_camera(camera_id)
        if camera_config['@proto'] != 'v4l2':
            def on_response(content):
                if content:
                    self.set_header('Content-Type', 'image/jpeg')
                    
                else:
                    self.set_header('Content-Type', 'image/svg+xml')
                    content = open(os.path.join(settings.STATIC_PATH, 'img', 'no-preview.svg')).read()
                
                self.finish(content)
            
            remote.get_media_preview(camera_config, on_response, filename=filename, media_type='picture',
                    width=self.get_argument('width', None),
                    height=self.get_argument('height', None))
        
        else:
            content = mediafiles.get_media_preview(camera_config, filename, 'picture',
                    width=self.get_argument('width', None),
                    height=self.get_argument('height', None))
            
            if content:
                self.set_header('Content-Type', 'image/jpeg')
                
            else:
                self.set_header('Content-Type', 'image/svg+xml')
                content = open(os.path.join(settings.STATIC_PATH, 'img', 'no-preview.svg')).read()
                
            self.finish(content)
    
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
    
    @BaseHandler.auth()
    def list(self, camera_id):
        logging.debug('listing movies for camera %(id)s' % {'id': camera_id})
        
        if camera_id not in config.get_camera_ids():
            raise HTTPError(404, 'no such camera')
        
        camera_config = config.get_camera(camera_id)
        if camera_config['@proto'] != 'v4l2':
            def on_response(remote_list):
                if remote_list is None:
                    return self.finish_json({'error': 'Failed to get movie list for %(url)s.' % {
                            'url': utils.make_camera_url(camera_config)}})

                self.finish_json(remote_list)
            
            remote.list_media(camera_config, on_response, media_type='movie', prefix=self.get_argument('prefix', None))
        
        else:
            def on_media_list(media_list):
                if media_list is None:
                    return self.finish_json({'error': 'Failed to get movies list.'})

                self.finish_json({
                    'mediaList': media_list,
                    'cameraName': camera_config['@name']
                })
            
            mediafiles.list_media(camera_config, media_type='movie',
                    callback=on_media_list, prefix=self.get_argument('prefix', None))
            
    @BaseHandler.auth()
    def download(self, camera_id, filename):
        logging.debug('downloading movie %(filename)s of camera %(id)s' % {
                'filename': filename, 'id': camera_id})
        
        if camera_id not in config.get_camera_ids():
            raise HTTPError(404, 'no such camera')
        
        camera_config = config.get_camera(camera_id)
        if camera_config['@proto'] != 'v4l2':
            def on_response(response):
                if response is None:
                    return self.finish_json({'error': 'Failed to download movie from %(url)s.' % {
                            'url': utils.make_camera_url(camera_config)}})

                pretty_filename = os.path.basename(filename) # no camera name available w/o additional request
                self.set_header('Content-Type', 'video/mpeg')
                self.set_header('Content-Disposition', 'attachment; filename=' + pretty_filename + ';')
                
                self.finish(response)

            remote.get_media_content(camera_config, on_response, filename=filename, media_type='movie')
            
        else:
            content = mediafiles.get_media_content(camera_config, filename, 'movie')
            
            pretty_filename = camera_config['@name'] + '_' + os.path.basename(filename)
            self.set_header('Content-Type', 'video/mpeg')
            self.set_header('Content-Disposition', 'attachment; filename=' + pretty_filename + ';')
            
            self.finish(content)

    @BaseHandler.auth()
    def preview(self, camera_id, filename):
        logging.debug('previewing movie %(filename)s of camera %(id)s' % {
                'filename': filename, 'id': camera_id})
        
        if camera_id not in config.get_camera_ids():
            raise HTTPError(404, 'no such camera')
        
        camera_config = config.get_camera(camera_id)
        if camera_config['@proto'] != 'v4l2':
            def on_response(content):
                if content:
                    self.set_header('Content-Type', 'image/jpeg')
                    
                else:
                    self.set_header('Content-Type', 'image/svg+xml')
                    content = open(os.path.join(settings.STATIC_PATH, 'img', 'no-preview.svg')).read()

                self.finish(content)
            
            remote.get_media_preview(camera_config, on_response, filename=filename, media_type='movie',
                    width=self.get_argument('width', None),
                    height=self.get_argument('height', None))
        
        else:
            content = mediafiles.get_media_preview(camera_config, filename, 'movie',
                    width=self.get_argument('width', None),
                    height=self.get_argument('height', None))
            
            if content:
                self.set_header('Content-Type', 'image/jpeg')
                
            else:
                self.set_header('Content-Type', 'image/svg+xml')
                content = open(os.path.join(settings.STATIC_PATH, 'img', 'no-preview.svg')).read()
            
            self.finish(content)


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
