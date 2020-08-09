
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

from motioneye import config
from motioneye import utils
from motioneye import mediafiles
from motioneye import motionctl
from motioneye import tasks
from motioneye import uploadservices
from motioneye.handlers.base import BaseHandler


__all__ = ('RelayEventHandler',)


class RelayEventHandler(BaseHandler):
    @BaseHandler.auth(admin=True)
    def post(self):
        event = self.get_argument('event')
        motion_camera_id = int(self.get_argument('motion_camera_id'))

        camera_id = motionctl.motion_camera_id_to_camera_id(motion_camera_id)
        if camera_id is None:
            logging.debug('ignoring event for unknown motion camera id %s' % motion_camera_id)
            return self.finish_json()

        else:
            logging.debug('received relayed event %(event)s for motion camera id %(id)s (camera id %(cid)s)' % {
                'event': event, 'id': motion_camera_id, 'cid': camera_id})

        camera_config = config.get_camera(camera_id)
        if not utils.is_local_motion_camera(camera_config):
            logging.warning('ignoring event for non-local camera with id %s' % camera_id)
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
            tasks.add(5, mediafiles.make_movie_preview, tag='make_movie_preview(%s)' % filename,
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
            logging.warning('unknown event %s' % event)

        self.finish_json()

    def upload_media_file(self, filename, camera_id, camera_config):
        service_name = camera_config['@upload_service']

        tasks.add(5, uploadservices.upload_media_file, tag='upload_media_file(%s)' % filename,
                  camera_id=camera_id, service_name=service_name,
                  camera_name=camera_config['camera_name'],
                  target_dir=camera_config['@upload_subfolders'] and camera_config['target_dir'],
                  filename=filename)
