
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
import os

from tornado.web import HTTPError

from motioneye import config
from motioneye import remote
from motioneye import mediafiles
from motioneye import settings
from motioneye import utils
from motioneye.handlers.base import BaseHandler


__all__ = ('MovieHandler',)


class MovieHandler(BaseHandler):

    async def get(self, camera_id, op, filename=None):
        if camera_id is not None:
            camera_id = int(camera_id)
            if camera_id not in config.get_camera_ids():
                raise HTTPError(404, 'no such camera')

        if op == 'list':
            self.list(camera_id)

        elif op == 'preview':
            self.preview(camera_id, filename)

        else:
            raise HTTPError(400, 'unknown operation')

    async def post(self, camera_id, op, filename=None, group=None):
        if group == '/':  # ungrouped
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
        if utils.is_local_motion_camera(camera_config):
            def on_media_list(media_list):
                if media_list is None:
                    return self.finish_json({'error': 'Failed to get movies list.'})

                self.finish_json({
                    'mediaList': media_list,
                    'cameraName': camera_config['camera_name']
                })

            mediafiles.list_media(camera_config, media_type='movie',
                                  callback=on_media_list, prefix=self.get_argument('prefix', None))

        elif utils.is_remote_camera(camera_config):
            def on_response(remote_list=None, error=None):
                if error:
                    return self.finish_json({'error': 'Failed to get movie list for %(url)s: %(msg)s.' % {
                        'url': remote.pretty_camera_url(camera_config), 'msg': error}})

                self.finish_json(remote_list)

            remote.list_media(camera_config, media_type='movie', prefix=self.get_argument('prefix', None),
                              callback=on_response)

        else:  # assuming simple mjpeg camera
            raise HTTPError(400, 'unknown operation')

    @BaseHandler.auth()
    def preview(self, camera_id, filename):
        logging.debug('previewing movie %(filename)s of camera %(id)s' % {
            'filename': filename, 'id': camera_id})

        camera_config = config.get_camera(camera_id)
        if utils.is_local_motion_camera(camera_config):
            content = mediafiles.get_media_preview(camera_config, filename, 'movie',
                                                   width=self.get_argument('width', None),
                                                   height=self.get_argument('height', None))

            if content:
                self.set_header('Content-Type', 'image/jpeg')

            else:
                self.set_header('Content-Type', 'image/svg+xml')
                content = open(os.path.join(settings.STATIC_PATH, 'img', 'no-preview.svg')).read()

            self.finish(content)

        elif utils.is_remote_camera(camera_config):
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

        else:  # assuming simple mjpeg camera
            raise HTTPError(400, 'unknown operation')

    @BaseHandler.auth(admin=True)
    def delete(self, camera_id, filename):
        logging.debug('deleting movie %(filename)s of camera %(id)s' % {
            'filename': filename, 'id': camera_id})

        camera_config = config.get_camera(camera_id)
        if utils.is_local_motion_camera(camera_config):
            try:
                mediafiles.del_media_content(camera_config, filename, 'movie')
                self.finish_json()

            except Exception as e:
                self.finish_json({'error': str(e)})

        elif utils.is_remote_camera(camera_config):
            def on_response(response=None, error=None):
                if error:
                    return self.finish_json({'error': 'Failed to delete movie from %(url)s: %(msg)s.' % {
                        'url': remote.pretty_camera_url(camera_config), 'msg': error}})

                self.finish_json()

            remote.del_media_content(camera_config, filename=filename, media_type='movie', callback=on_response)

        else:  # assuming simple mjpeg camera
            raise HTTPError(400, 'unknown operation')

    @BaseHandler.auth(admin=True)
    def delete_all(self, camera_id, group):
        logging.debug('deleting movie group "%(group)s" of camera %(id)s' % {
            'group': group or 'ungrouped', 'id': camera_id})

        camera_config = config.get_camera(camera_id)
        if utils.is_local_motion_camera(camera_config):
            try:
                mediafiles.del_media_group(camera_config, group, 'movie')
                self.finish_json()

            except Exception as e:
                self.finish_json({'error': str(e)})

        elif utils.is_remote_camera(camera_config):
            def on_response(response=None, error=None):
                if error:
                    return self.finish_json({'error': 'Failed to delete movie group at %(url)s: %(msg)s.' % {
                        'url': remote.pretty_camera_url(camera_config), 'msg': error}})

                self.finish_json()

            remote.del_media_group(camera_config, group=group, media_type='movie', callback=on_response)

        else:  # assuming simple mjpeg camera
            raise HTTPError(400, 'unknown operation')
