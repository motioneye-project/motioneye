
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
import tempfile
import time

from tornado.web import HTTPError, StaticFileHandler

from motioneye import config
from motioneye import remote
from motioneye import mediafiles
from motioneye import utils
from motioneye.handlers.base import BaseHandler


__all__ = ('MoviePlaybackHandler', 'MovieDownloadHandler')


# support fetching movies with authentication
class MoviePlaybackHandler(StaticFileHandler, BaseHandler):
    tmpdir = tempfile.gettempdir() + '/MotionEye'
    if not os.path.exists(tmpdir):
        os.mkdir(tmpdir)

    @BaseHandler.auth()
    async def get(self, camera_id, filename=None, include_body=True):
        logging.debug('downloading movie %(filename)s of camera %(id)s' % {
            'filename': filename, 'id': camera_id})

        self.pretty_filename = os.path.basename(filename)

        if camera_id is not None:
            camera_id = int(camera_id)
            if camera_id not in config.get_camera_ids():
                raise HTTPError(404, 'no such camera')

        camera_config = config.get_camera(camera_id)

        if utils.is_local_motion_camera(camera_config):
            filename = mediafiles.get_media_path(camera_config, filename, 'movie')
            self.pretty_filename = camera_config['camera_name'] + '_' + self.pretty_filename
            await StaticFileHandler.get(self, filename, include_body=include_body)
            return

        elif utils.is_remote_camera(camera_config):
            # we will cache the movie since it takes a while to fetch from the remote camera
            # and we may be going to play it back in the browser, which will fetch the video in chunks
            tmpfile = self.tmpdir + '/' + self.pretty_filename
            if os.path.isfile(tmpfile):
                # have a cached copy, update the timestamp so it's not flushed
                import time
                mtime = os.stat(tmpfile).st_mtime
                os.utime(tmpfile, (time.time(), mtime))
                await StaticFileHandler.get(self, tmpfile, include_body=include_body)
                return

            resp = await remote.get_media_content(camera_config, filename, media_type='movie')
            if resp.error:
                return self.finish_json({'error': 'Failed to download movie from %(url)s: %(msg)s.' % {
                    'url': remote.pretty_camera_url(camera_config), 'msg': resp.error}})

            # check if the file has been created by another request while we were fetching the movie
            if not os.path.isfile(tmpfile):
                tmp = open(tmpfile, 'wb')
                tmp.write(resp.result)
                tmp.close()

            await StaticFileHandler.get(self, tmpfile, include_body=include_body)
            return

        else:  # assuming simple mjpeg camera
            raise HTTPError(400, 'unknown operation')

    def on_finish(self):
        # delete any cached file older than an hour
        stale_time = time.time() - (60 * 60)
        try:
            for f in os.listdir(self.tmpdir):
                f = os.path.join(self.tmpdir, f)
                if os.path.isfile(f) and os.stat(f).st_atime <= stale_time:
                    os.remove(f)
        except:
            logging.error('could not delete temp file', exc_info=True)
            pass

    def get_absolute_path(self, root, path):
        return path

    def validate_absolute_path(self, root, absolute_path):
        return absolute_path


class MovieDownloadHandler(MoviePlaybackHandler):
    def set_extra_headers(self, filename):
        if self.get_status() in (200, 304):
            self.set_header('Content-Disposition', 'attachment; filename=' + self.pretty_filename + ';')
            self.set_header('Expires', '0')
