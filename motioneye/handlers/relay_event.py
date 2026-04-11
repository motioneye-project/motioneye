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

from motioneye import config, mediafiles, motionctl, tasks, uploadservices, utils
from motioneye.handlers.base import BaseHandler

__all__ = ('RelayEventHandler',)


class RelayEventHandler(BaseHandler):
    @BaseHandler.auth(admin=True)
    def post(self) -> None:
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

        filename: str | None = self.get_argument('filename')
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
                self.upload_media_file(filename, camera_id, camera_config)

        elif event == 'picture_save':
            # upload to external service
            if camera_config['@upload_enabled'] and camera_config['@upload_picture']:
                self.upload_media_file(filename, camera_id, camera_config)

        else:
            logging.warning(f'unknown event {event}')

        self.finish_json()

    def upload_media_file(self, filename, camera_id, camera_config):
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
        )
