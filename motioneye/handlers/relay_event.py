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

from motioneye import config, mediafiles, motionctl, tasks, uploadservices, utils
from motioneye.handlers import telegram
from motioneye.handlers.base import BaseHandler

__all__ = ('RelayEventHandler',)


class RelayEventHandler(BaseHandler):
    @BaseHandler.auth(admin=True)
    async def post(self):
        event = self.get_argument('event')
        motion_camera_id = int(self.get_argument('motion_camera_id'))

        camera_id = motionctl.motion_camera_id_to_camera_id(motion_camera_id)
        if camera_id is None:
            logging.debug(
                'ignoring event for unknown motion camera id %s' % motion_camera_id
            )
            return self.finish_json()

        else:
            logging.debug(
                'received relayed event {event} for motion camera id {id} (camera id {cid})'.format(
                    event=event, id=motion_camera_id, cid=camera_id
                )
            )

        camera_config = config.get_camera(camera_id)
        if not utils.is_local_motion_camera(camera_config):
            logging.warning(
                'ignoring event for non-local camera with id %s' % camera_id
            )
            return self.finish_json()

        # needed for specific motion event recognition
        event_id = self.get_argument('event_id')
        moment = self.get_argument('moment')

        if event == 'start':
            if not camera_config['@motion_detection']:
                logging.debug(
                    'ignoring start event for camera with id %s and motion detection disabled'
                    % camera_id
                )
                return self.finish_json()

            motionctl.set_motion_detected(camera_id, True)

        elif event == 'stop':
            motionctl.set_motion_detected(camera_id, False)

            # notify telegram handler event stop
            await self.handle_telegram_notification(camera_id, camera_config, moment, event, event_id, "")
       
        elif event == 'movie_end':
            filename = self.get_argument('filename')

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
            filename = self.get_argument('filename')

            # upload to external service
            if camera_config['@upload_enabled'] and camera_config['@upload_picture']:
                self.upload_media_file(filename, camera_id, camera_config)

            # send media to telegram 
            await self.handle_telegram_notification(camera_id, camera_config, moment, event, event_id, filename)

        else:
            logging.warning('unknown event %s' % event)

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

    async def handle_telegram_notification(self, camera_id, camera_config, moment, event, event_id, filename):

        # telegram notifications should only be triggered when motion detects well, motion :)
        # below checks should allow media only when capture mode in GUI is set to "Motion Triggered" and "Motion Triggered (one picture)"
        
        if (camera_config["picture_output"] != False and camera_config['emulate_motion'] != True and camera_config['snapshot_interval'] == 0):
            if (camera_config['@telegram_notifications_enabled']): 
                if (camera_config['@telegram_notifications_api'] and camera_config['@telegram_notifications_chat_id']):
                    th = telegram.TelegramHandler.get_instance()
                    await th.add_media({"camera_id" : camera_id, "camera_config" : camera_config, "moment" : moment, "event" : event, "event_id" : event_id, "file_name" : filename})
                else:
                    logging.warning("telegram notifications are enabled, but some of telegram_notifications parameters are not set")
                    return self.finish_json()
