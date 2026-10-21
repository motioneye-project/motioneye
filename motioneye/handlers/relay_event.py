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

from __future__ import annotations

import logging
import os

from motioneye import (
    config,
    mediafiles,
    motionctl,
    settings,
    tasks,
    uploadservices,
    utils,
)
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
        # (internal relay from Motion daemon only). If motionEye listens on a specific
        # address, the relay script connects to that one instead.
        client_ip = self.request.remote_ip
        if client_ip not in ('127.0.0.1', 'localhost', '::1', settings.LISTEN):
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
            return None

        else:
            logging.debug(
                f'received relayed event {event} for motion camera id {motion_camera_id} (camera id {camera_id})'
            )

        camera_config: dict = config.get_camera(camera_id)
        if not utils.is_local_motion_camera(camera_config):
            logging.warning(f'ignoring event for non-local camera with id {camera_id}')
            self.finish_json()
            return None

        filename: str | None = self.get_argument('filename')
        if filename is not None:
            target_dir: str = camera_config['target_dir']
            # motion sends an absolute path, motionEye passes it on relative to
            # the camera dir and joins it again only for file operations
            filename = filename.removeprefix(target_dir + os.sep)
            utils.validate_paths(filename, target_dir=target_dir)

        if event == 'start':
            if not camera_config['@motion_detection']:
                logging.debug(
                    f'ignoring start event for camera with id {camera_id} and motion detection disabled'
                )
                self.finish_json()
                return None

            motionctl.set_motion_detected(camera_id, True)

        elif event == 'stop':
            motionctl.set_motion_detected(camera_id, False)

        elif event == 'movie_end':
            # generate preview (thumbnail)
            tasks.add(
                5,
                mediafiles.make_movie_preview,
                tag=f'make_movie_preview({filename})',
                camera_config=camera_config,
                rel_path=filename,
            )

            # upload to external service
            if camera_config['@upload_enabled'] and camera_config['@upload_movie']:
                self._upload_media_file(filename, camera_id, camera_config)

        elif event == 'picture_save':
            # upload to external service
            if camera_config['@upload_enabled'] and camera_config['@upload_picture']:
                self._upload_media_file(filename, camera_id, camera_config)

        else:
            logging.warning(f'unknown event {event}')

        self.finish_json()

        return None

    def _upload_media_file(self, filename, camera_id, camera_config):
        service_name = camera_config['@upload_service']

        tasks.add(
            5,
            uploadservices.upload_media_file,
            tag=f'upload_media_file({filename})',
            camera_id=camera_id,
            service_name=service_name,
            camera_name=camera_config['camera_name'],
            target_dir=camera_config['@upload_subfolders']
            and camera_config['target_dir'],
            # the upload subsystem still works with the absolute path
            filename=os.path.join(camera_config['target_dir'], filename),
            clean_uploaded=camera_config['@clean_uploaded'],
        )
