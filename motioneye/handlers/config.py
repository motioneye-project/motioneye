# Copyright (c) 2020 Vlsarro
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
import socket

from tornado.ioloop import IOLoop
from tornado.web import HTTPError

from motioneye import (
    config,
    meyectl,
    motionctl,
    remote,
    settings,
    tasks,
    template,
    uploadservices,
    utils,
)
from motioneye.controls import mmalctl, smbctl, tzctl, v4l2ctl
from motioneye.controls.powerctl import PowerControl
from motioneye.handlers.base import BaseHandler
from motioneye.utils.mjpeg import test_mjpeg_url
from motioneye.utils.rtmp import test_rtmp_url
from motioneye.utils.rtsp import test_rtsp_url

__all__ = ('ConfigHandler',)


class ConfigHandler(BaseHandler):
    async def get(self, camera_id=None, op=None):
        config.invalidate_monitor_commands()

        if camera_id is not None:
            camera_id = int(camera_id)

        if op == 'get':
            await self.get_config(camera_id)
            return

        elif op == 'list':
            await self.list()
            return

        elif op == 'backup':
            return self.backup()

        elif op == 'authorize':
            return self.authorize(camera_id)

        else:
            raise HTTPError(400, 'unknown operation')

    async def post(self, camera_id=None, op=None):
        if camera_id is not None:
            camera_id = int(camera_id)

        if op == 'set':
            await self.set_config(camera_id)
            return

        elif op == 'add':
            await self.add_camera()
            return

        elif op == 'rem':
            return self.rem_camera(camera_id)

        elif op == 'restore':
            return self.restore()

        elif op == 'test':
            await self.test(camera_id)

        else:
            raise HTTPError(400, 'unknown operation')

    @BaseHandler.auth(admin=True)
    async def get_config(self, camera_id):
        if camera_id:
            logging.debug(f'getting config for camera {camera_id}')

            if camera_id not in config.get_camera_ids():
                raise HTTPError(404, 'no such camera')

            local_config = config.get_camera(camera_id)
            if utils.is_local_motion_camera(local_config):
                ui_config = config.motion_camera_dict_to_ui(local_config)

                return self.finish_json(ui_config)

            elif utils.is_remote_camera(local_config):
                resp = await remote.get_config(local_config)
                if resp.error:
                    msg = 'Failed to get remote camera configuration for {url}: {msg}.'.format(
                        url=remote.pretty_camera_url(local_config), msg=resp.error
                    )
                    return self.finish_json_with_error(msg)

                for key, value in list(local_config.items()):
                    resp.remote_ui_config[key.replace('@', '')] = value

                # replace the real device url with the remote camera path
                resp.remote_ui_config['device_url'] = remote.pretty_camera_url(
                    local_config
                )
                return self.finish_json(resp.remote_ui_config)

            else:  # assuming simple mjpeg camera
                ui_config = config.simple_mjpeg_camera_dict_to_ui(local_config)

                return self.finish_json(ui_config)

        else:
            logging.debug('getting main config')

            ui_config = config.main_dict_to_ui(config.get_main())
            return self.finish_json(ui_config)

    @BaseHandler.auth(admin=True)
    async def set_config(self, camera_id):
        try:
            ui_config = json.loads(self.request.body)

        except Exception as e:
            logging.error(f'could not decode json: {str(e)}')

            raise

        camera_ids = config.get_camera_ids()

        async def set_camera_config(camera_id, ui_config, on_finish):
            logging.debug(f'setting config for camera {camera_id}...')

            if camera_id not in camera_ids:
                raise HTTPError(404, 'no such camera')

            local_config = config.get_camera(camera_id)
            if utils.is_local_motion_camera(local_config):
                local_config = config.motion_camera_ui_to_dict(ui_config, local_config)

                config.set_camera(camera_id, local_config)

                on_finish(None, True)  # (no error, motion needs restart)

            elif utils.is_remote_camera(local_config):
                # update the camera locally
                local_config['@enabled'] = ui_config['enabled']
                config.set_camera(camera_id, local_config)

                if 'name' in ui_config:

                    def on_finish_wrapper(e=None):
                        return on_finish(e, False)

                    ui_config['enabled'] = True  # never disable the camera remotely
                    result = await remote.set_config(local_config, ui_config)
                    return on_finish(result, False)

                else:
                    # when the ui config supplied has only the enabled state
                    # and no useful fields (such as "name"),
                    # the camera was probably disabled due to errors
                    on_finish(None, False)

            else:  # assuming simple mjpeg camera
                local_config = config.simple_mjpeg_camera_ui_to_dict(
                    ui_config, local_config
                )

                config.set_camera(camera_id, local_config)

                on_finish(None, False)  # (no error, motion doesn't need restart)

        def set_main_config(ui_config):
            logging.debug('setting main config...')

            old_main_config = config.get_main()
            old_admin_username = old_main_config.get('@admin_username')
            old_normal_username = old_main_config.get('@normal_username')
            old_lang = old_main_config.get('@lang')

            main_config = config.main_ui_to_dict(ui_config)
            main_config.setdefault('camera', old_main_config.get('camera', []))

            admin_username = main_config.get('@admin_username')
            admin_password = main_config.get('@admin_password')

            normal_username = main_config.get('@normal_username')
            normal_password = main_config.get('@normal_password')
            lang = main_config.get('@lang')

            additional_configs = config.get_additional_structure(camera=False)[1]
            reboot_config_names = [
                ('@_' + c['name'])
                for c in list(additional_configs.values())
                if c.get('reboot')
            ]
            reboot = bool(
                [
                    k
                    for k in reboot_config_names
                    if old_main_config.get(k) != main_config.get(k)
                ]
            )

            config.set_main(main_config)

            reload = False
            restart = False

            if lang != old_lang:
                logging.debug('lang changed, reload needed')
                meyectl.load_l10n()
                template._reload_lang()

                reload = True

            if admin_username != old_admin_username or admin_password is not None:
                logging.debug('admin credentials changed, reload needed')

                reload = True

            if normal_username != old_normal_username or normal_password is not None:
                logging.debug(
                    'surveillance credentials changed, all camera configs must be updated'
                )

                # reconfigure all local cameras to update the stream authentication options
                for camera_id in config.get_camera_ids():
                    local_config = config.get_camera(camera_id)
                    if not utils.is_local_motion_camera(local_config):
                        continue

                    ui_config = config.motion_camera_dict_to_ui(local_config)
                    local_config = config.motion_camera_ui_to_dict(
                        ui_config, local_config
                    )

                    config.set_camera(camera_id, local_config)

                    restart = True

            if reboot and settings.ENABLE_REBOOT:
                logging.debug('system settings changed, reboot needed')

            else:
                reboot = False

            return {'reload': reload, 'reboot': reboot, 'restart': restart}

        reload = False  # indicates that browser should reload the page
        reboot = [False]  # indicates that the server will reboot immediately
        restart = [
            False
        ]  # indicates that the local motion instance was modified and needs to be restarted
        error = [None]

        def finish():
            if reboot[0]:
                if settings.ENABLE_REBOOT:

                    def call_reboot():
                        PowerControl.reboot()

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
            if camera_id == 0:  # multiple camera configs
                if len(ui_config) > 1:
                    logging.debug('setting multiple configs')

                elif len(ui_config) == 0:
                    logging.warning('no configuration to set')

                    return self.finish()

                so_far = [0]

                def check_finished(e, r):
                    restart[0] = restart[0] or r
                    error[0] = error[0] or e
                    so_far[0] += 1

                    if so_far[0] >= len(ui_config):  # finished
                        finish()

                # make sure main config is handled first
                items = list(ui_config.items())
                items.sort(key=lambda key_cfg: key_cfg[0] != 'main')

                for key, cfg in items:
                    if key == 'main':
                        result = set_main_config(cfg)
                        reload = result['reload'] or reload
                        reboot[0] = result['reboot'] or reboot[0]
                        restart[0] = result['restart'] or restart[0]
                        check_finished(None, False)

                    else:
                        await set_camera_config(int(key), cfg, check_finished)

            else:  # single camera config

                def on_finish(e, r):
                    error[0] = e
                    restart[0] = r
                    finish()

                await set_camera_config(camera_id, ui_config, on_finish)

        else:  # main config
            result = set_main_config(ui_config)
            reload = result['reload']
            reboot[0] = result['reboot']
            restart[0] = result['restart']

    def _handle_list_cameras_response(self, resp: utils.GetCamerasResponse):
        if resp.error:
            return self.finish_json_with_error(resp.error)
        else:
            return self.finish_json({'cameras': resp.cameras})

    def finish_json_with_error(self, error_msg: str):
        return self.finish_json({'error': error_msg})

    def check_finished(self, cameras: list, length: list) -> bool:
        if len(cameras) == length[0]:
            cameras.sort(key=lambda c: c['id'])
            self.finish_json({'cameras': cameras})
            return True
        else:
            return False

    def _handle_get_config_response(
        self,
        camera_id,
        local_config,
        resp: utils.GetConfigResponse,
        cameras: list,
        length: list,
    ) -> None:
        if resp.error:
            cameras.append(
                {
                    'id': camera_id,
                    'name': '&lt;' + remote.pretty_camera_url(local_config) + '&gt;',
                    'enabled': False,
                    'streaming_framerate': 1,
                    'framerate': 1,
                }
            )

        else:
            resp.remote_ui_config['id'] = camera_id

            if not resp.remote_ui_config['enabled'] and local_config['@enabled']:
                # if a remote camera is disabled, make sure it's disabled locally as well
                local_config['@enabled'] = False
                config.set_camera(camera_id, local_config)

            elif resp.remote_ui_config['enabled'] and not local_config['@enabled']:
                # if a remote camera is locally disabled, make sure the remote config says the same thing
                resp.remote_ui_config['enabled'] = False

            for key, value in list(local_config.items()):
                resp.remote_ui_config[key.replace('@', '')] = value

            cameras.append(resp.remote_ui_config)

        return self.check_finished(cameras, length)

    @BaseHandler.auth()
    async def list(self):
        logging.debug('listing cameras')

        proto = self.get_argument('proto')
        if proto == 'motioneye':  # remote listing
            return self._handle_list_cameras_response(
                await remote.list_cameras(self.get_all_arguments())
            )

        elif proto == 'netcam':
            scheme = self.get_argument('scheme', 'http')

            if scheme in ['http', 'https', 'mjpeg']:
                resp = await test_mjpeg_url(
                    self.get_all_arguments(), auth_modes=['basic'], allow_jpeg=True
                )
                return self._handle_list_cameras_response(resp)

            elif scheme == 'rtsp':
                resp = await test_rtsp_url(self.get_all_arguments())
                return self._handle_list_cameras_response(resp)

            elif scheme == 'rtmp':
                resp = test_rtmp_url(self.get_all_arguments())
                return self._handle_list_cameras_response(resp)

            else:
                return self.finish_json_with_error(f'protocol {scheme} not supported')

        elif proto == 'mjpeg':
            resp = await test_mjpeg_url(
                self.get_all_arguments(),
                auth_modes=['basic', 'digest'],
                allow_jpeg=False,
            )
            return self._handle_list_cameras_response(resp)

        elif proto == 'v4l2':
            configured_devices = set()
            for camera_id in config.get_camera_ids():
                data = config.get_camera(camera_id)
                if utils.is_v4l2_camera(data):
                    configured_devices.add(data['videodevice'])

            cameras = [
                {'id': d[1], 'name': d[2]}
                for d in v4l2ctl.list_devices()
                if (d[0] not in configured_devices) and (d[1] not in configured_devices)
            ]

            return self.finish_json({'cameras': cameras})

        elif proto == 'mmal':
            configured_devices = set()
            for camera_id in config.get_camera_ids():
                data = config.get_camera(camera_id)
                if utils.is_mmal_camera(data):
                    configured_devices.add(data['mmalcam_name'])

            cameras = [
                {'id': d[0], 'name': d[1]}
                for d in mmalctl.list_devices()
                if (d[0] not in configured_devices)
            ]

            return self.finish_json({'cameras': cameras})

        else:  # assuming local motionEye camera listing
            cameras = []
            camera_ids = config.get_camera_ids()
            if not config.get_main().get('@enabled'):
                camera_ids = []

            length = [len(camera_ids)]

            for camera_id in camera_ids:
                local_config = config.get_camera(camera_id)
                if local_config is None:
                    continue

                if utils.is_local_motion_camera(local_config):
                    ui_config = config.motion_camera_dict_to_ui(local_config)
                    cameras.append(ui_config)
                    if self.check_finished(cameras, length):
                        return

                elif utils.is_remote_camera(local_config):
                    if (
                        local_config.get('@enabled')
                        or self.get_argument('force', None) == 'true'
                    ):
                        resp = await remote.get_config(local_config)
                        if self._handle_get_config_response(
                            camera_id, local_config, resp, cameras, length
                        ):
                            return

                    else:  # don't try to reach the remote of the camera is disabled
                        if self._handle_get_config_response(
                            camera_id,
                            local_config,
                            utils.GetConfigResponse(None, error=True),
                            cameras,
                            length,
                        ):
                            return

                else:  # assuming simple mjpeg camera
                    ui_config = config.simple_mjpeg_camera_dict_to_ui(local_config)
                    cameras.append(ui_config)
                    if self.check_finished(cameras, length):
                        return

            return self.finish_json({'cameras': cameras})

    @BaseHandler.auth(admin=True)
    async def add_camera(self):
        logging.debug('adding new camera')

        try:
            device_details = json.loads(self.request.body)

        except Exception as e:
            logging.error(f'could not decode json: {str(e)}')

            raise

        camera_config = config.add_camera(device_details)

        if utils.is_local_motion_camera(camera_config):
            motionctl.stop()

            if settings.SMB_SHARES:
                stop, start = smbctl.update_mounts()  # @UnusedVariable

                if start:
                    motionctl.start()

            else:
                motionctl.start()

            ui_config = config.motion_camera_dict_to_ui(camera_config)

            return self.finish_json(ui_config)

        elif utils.is_remote_camera(camera_config):
            resp = await remote.get_config(camera_config)
            if resp.error:
                return self.finish_json_with_error(resp.error)

            for key, value in list(camera_config.items()):
                resp.remote_ui_config[key.replace('@', '')] = value

            return self.finish_json(resp.remote_ui_config)

        else:  # assuming simple mjpeg camera
            ui_config = config.simple_mjpeg_camera_dict_to_ui(camera_config)

            return self.finish_json(ui_config)

    @BaseHandler.auth(admin=True)
    def rem_camera(self, camera_id):
        logging.debug(f'removing camera {camera_id}')

        local = utils.is_local_motion_camera(config.get_camera(camera_id))
        config.rem_camera(camera_id)

        if local:
            motionctl.stop()
            motionctl.start()

        return self.finish_json()

    @BaseHandler.auth(admin=True)
    def backup(self):
        content = config.backup()

        if not content:
            raise Exception('failed to create backup file')

        filename = 'motioneye-config.tar.gz'
        self.set_header('Content-Type', 'application/x-compressed')
        self.set_header('Content-Disposition', 'attachment; filename=' + filename + ';')

        return self.finish(content)

    @BaseHandler.auth(admin=True)
    def restore(self):
        try:
            content = self.request.files['files'][0]['body']

        except KeyError:
            raise HTTPError(400, 'file attachment required')

        result = config.restore(content)
        if result:
            return self.finish_json({'ok': True, 'reboot': result['reboot']})

        else:
            return self.finish_json({'ok': False})

    @classmethod
    def _on_test_result(cls, result):
        upload_service_test_info = getattr(cls, '_upload_service_test_info', None)
        cls._upload_service_test_info = None

        if not upload_service_test_info:
            return logging.warning('no pending upload service test request')

        (request_handler, service_name) = upload_service_test_info

        if result is True:
            logging.info(f'accessing {service_name} succeeded.result {result}')
            return request_handler.finish_json()

        else:
            logging.warning(f'accessing {service_name} failed: {result}')
            return request_handler.finish_json({'error': result})

    @BaseHandler.auth(admin=True)
    async def test(self, camera_id):
        what = self.get_argument('what')
        data = self.get_all_arguments()
        camera_config = config.get_camera(camera_id)

        if utils.is_local_motion_camera(camera_config):
            if what == 'upload_service':
                service_name = data['service']
                ConfigHandler._upload_service_test_info = (self, service_name)

                result = uploadservices.test_access(
                    camera_id=camera_id, service_name=service_name, data=data
                )
                logging.debug(f'test access {service_name} result {result}')
                if result is True:
                    logging.info(f'accessing {service_name} succeeded.result {result}')
                    return self.finish_json()
                else:
                    logging.warning(f'accessing {service_name} failed: {result}')
                    return self.finish_json({'error': result})

            elif what == 'email':
                import smtplib

                from motioneye import sendmail

                logging.debug('testing notification email')

                try:
                    subject = sendmail.subjects['motion_start']
                    message = sendmail.messages['motion_start']
                    format_dict = {
                        'camera': camera_config['camera_name'],
                        'hostname': socket.gethostname(),
                        'moment': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    }
                    if settings.LOCAL_TIME_FILE:
                        format_dict['timezone'] = tzctl.get_time_zone()

                    else:
                        format_dict['timezone'] = 'local time'

                    message = message % format_dict
                    subject = subject % format_dict

                    old_timeout = settings.SMTP_TIMEOUT
                    settings.SMTP_TIMEOUT = 10
                    sendmail.send_mail(
                        data['smtp_server'],
                        int(data['smtp_port']),
                        data['smtp_account'],
                        data['smtp_password'],
                        data['smtp_tls'],
                        data['from'],
                        [data['addresses']],
                        subject=subject,
                        message=message,
                        files=[],
                    )

                    settings.SMTP_TIMEOUT = old_timeout
                    logging.debug('notification email test succeeded')
                    return self.finish_json()

                except Exception as e:
                    if isinstance(e, smtplib.SMTPResponseException):
                        msg = e.smtp_error

                    else:
                        msg = str(e)

                    msg_lower = msg.lower()
                    if msg_lower.count('tls'):
                        msg = 'TLS might be required'

                    elif msg_lower.count('authentication'):
                        msg = 'authentication error'

                    elif msg_lower.count('name or service not known'):
                        msg = 'check SMTP server name'

                    elif msg_lower.count('connection refused'):
                        msg = 'check SMTP port'

                    logging.error(
                        'notification email test failed: %s' % msg, exc_info=True
                    )
                    return self.finish_json({'error': str(msg)})

            elif what == 'telegram':
                from motioneye import sendtelegram

                logging.debug('testing telegram notification')

                try:
                    message = 'This is a test of motionEye\'s telegram messaging'
                    sendtelegram.send_message(
                        data['api'], int(data['chatid']), message=message, files=[]
                    )

                    self.finish_json()

                    logging.debug('telegram notification test succeeded')

                except Exception as e:
                    msg = str(e)

                    msg_lower = msg.lower()
                    logging.error(
                        'telegram notification test failed: %s' % msg, exc_info=True
                    )
                    self.finish_json({'error': str(msg)})

            elif what == 'network_share':
                logging.debug(
                    'testing access to network share //{}/{}'.format(
                        data['server'], data['share']
                    )
                )

                try:
                    smbctl.test_share(
                        data['server'],
                        data['share'],
                        data['smb_ver'],
                        data['username'],
                        data['password'],
                        data['root_directory'],
                    )

                    logging.debug(
                        'access to network share //{}/{} succeeded'.format(
                            data['server'], data['share']
                        )
                    )
                    return self.finish_json()

                except Exception as e:
                    logging.error(
                        'access to network share //{}/{} failed: {}'.format(
                            data['server'], data['share'], e
                        )
                    )
                    return self.finish_json({'error': str(e)})

            else:
                raise HTTPError(400, 'unknown test %s' % what)

        elif utils.is_remote_camera(camera_config):
            resp = await remote.test(camera_config, data)
            if resp.result is True:
                return self.finish_json()
            else:
                result = resp.result or resp.error
                return self.finish_json_with_error(result)

        else:
            raise HTTPError(400, 'cannot test features on this type of camera')

    @BaseHandler.auth(admin=True)
    def authorize(self, camera_id):
        service_name = self.get_argument('service')
        if not service_name:
            raise HTTPError(400, 'service_name required')

        url = uploadservices.get_authorize_url(service_name)
        if not url:
            raise HTTPError(
                400, 'no authorization url for upload service %s' % service_name
            )

        logging.debug('redirected to authorization url %s' % url)
        self.redirect(url)
