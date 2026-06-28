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

import logging
from os import sep
from typing import Optional

from motioneye import config, mediafiles, motionctl, tasks, uploadservices, utils
from motioneye.handlers.base import BaseHandler

__all__ = ('RelayEventHandler',)


class RelayEventHandler(BaseHandler):
    def post(self) -> None:
        # Validate relay secret from header
        relay_secret = self.request.headers.get('X-Relay-Secret', '')
        expected_secret = config.get_relay_secret()

        if not relay_secret or relay_secret != expected_secret:
            logging.warning(
                f'relay event request with invalid secret from {self.request.remote_ip}'
            )
            self.set_status(403)
            return self.finish_json({'error': 'invalid_secret'})

        # Allow localhost/127.0.0.1 to call this endpoint without additional authentication
        # (internal relay from Motion daemon only)
        client_ip = self.request.remote_ip
        if client_ip not in ('127.0.0.1', 'localhost', '::1'):
            # Not localhost, require authentication
            user = self.current_user
            if user != 'admin':
                self.set_status(403)
                return self.finish_json({'error': 'unauthorized'})

        event = self.get_argument('event')
        motion_camera_id = int(self.get_argument('motion_camera_id'))

        camera_id = motionctl.motion_camera_id_to_camera_id(motion_camera_id)
        if camera_id is None:
            logging.debug(
                f'ignoring event for unknown motion camera id {motion_camera_id}'
            )
            self.finish_json()
            return

        else:
            logging.debug(
                f'received relayed event {event} for motion camera id {motion_camera_id} (camera id {camera_id})'
            )

        camera_config: dict = config.get_camera(camera_id)
        if not utils.is_local_motion_camera(camera_config):
            logging.warning(f'ignoring event for non-local camera with id {camera_id}')
            self.finish_json()
            return

        filename: Optional[str] = self.get_argument('filename')
        if filename is not None:
            target_dir: str = camera_config['target_dir']
            utils.validate_paths(
                filename.removeprefix(target_dir + sep),
                target_dir=target_dir,
            )

        if event == 'start':
            if not camera_config['@motion_detection']:
                logging.debug(
                    f'ignoring start event for camera with id {camera_id} and motion detection disabled'
                )
                self.finish_json()
                return

            motionctl.set_motion_detected(camera_id, True)

        elif event == 'stop':
            motionctl.set_motion_detected(camera_id, False)

        elif event == 'movie_end':
            # generate preview (thumbnail)
            tasks.add(
                5,
                mediafiles.make_movie_preview,
                tag='make_movie_preview(%s)' % filename,
                camera_config=camera_config,
                full_path=filename,
            )

            # upload to external service
            if camera_config['@upload_enabled'] and camera_config['@upload_movie']:
                self.upload_media_file(filename, camera_id, camera_config, 'movie')

        elif event == 'picture_save':
            # upload to external service
            if camera_config['@upload_enabled'] and camera_config['@upload_picture']:
                self.upload_media_file(filename, camera_id, camera_config, 'picture')

        else:
            logging.warning(f'unknown event {event}')

        self.finish_json()

    def upload_media_file(self, filename, camera_id, camera_config, media_type):
        service_name = camera_config['@upload_service']

        tasks.add(
            5,
            uploadservices.upload_media_file,
            tag='upload_media_file(%s)' % filename,
            camera_id=camera_id,
            service_name=service_name,
            camera_name=camera_config['camera_name'],
            target_dir=camera_config['@upload_subfolders']
            and camera_config['target_dir'],
            filename=filename,
            media_type=media_type,
            clean_uploaded=camera_config['@clean_uploaded'],
        )
