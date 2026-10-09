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
from asyncio import Lock, get_running_loop
from pathlib import Path
from tempfile import gettempdir
from time import time

from tornado.web import HTTPError, StaticFileHandler

from motioneye import config, mediafiles, remote, utils
from motioneye.handlers.base import BaseHandler

__all__ = ('MovieDownloadHandler', 'MoviePlaybackHandler')

# prevent concurrent remote fetching and movie cache writes
_remote_movie_cache_locks: dict[str, Lock] = {}


# support fetching movies with authentication
class MoviePlaybackHandler(StaticFileHandler, BaseHandler):
    tmpdir: str = gettempdir() + '/MotionEye'
    if not os.path.exists(tmpdir):
        os.mkdir(tmpdir)

    @BaseHandler.auth()
    @BaseHandler.peer_allowed()
    async def get(self, camera_id: str, filename: str, include_body=True):
        camera_id = int(camera_id)  # type: ignore[assignment]
        if camera_id not in config.get_camera_ids():
            raise HTTPError(404, 'no such camera')

        camera_config: dict = config.get_camera(camera_id)
        utils.validate_paths(
            filename,
            target_dir=(
                camera_config['target_dir']
                if utils.is_local_motion_camera(camera_config)
                else None
            ),
        )

        # block access to admin-only cameras for non-admin users
        if camera_config.get('@admin_only') and self.current_user not in [
            'admin',
            'peer',
        ]:
            raise HTTPError(
                403,
                f'GET access denied to admin-only camera "{camera_id}" for movie download "{filename}"',
            )

        logging.debug(f'downloading movie {filename} of camera {camera_id}')

        self.pretty_filename = os.path.basename(filename)

        if utils.is_local_motion_camera(camera_config):
            filename = mediafiles.get_media_path(camera_config, filename)
            self.pretty_filename = (
                camera_config['camera_name'] + '_' + self.pretty_filename
            )
            await StaticFileHandler.get(self, filename, include_body=include_body)
            return None

        elif utils.is_remote_camera(camera_config):
            # we will cache the movie since it takes a while to fetch from the remote camera
            # and we may be going to play it back in the browser, which will fetch the video in chunks
            tmpfile: str = self.tmpdir + '/' + self.pretty_filename
            lock: Lock = _remote_movie_cache_locks.setdefault(tmpfile, Lock())
            async with lock:
                if not os.path.isfile(tmpfile):
                    resp = await remote.get_media_content(
                        camera_config, filename, media_type='movie'
                    )
                    if resp.error:
                        msg: str = (
                            'failed to download movie from '
                            f'{remote.pretty_camera_url(camera_config)}: {resp.error}'
                        )
                        return self.finish_json({'error': msg})

                    await get_running_loop().run_in_executor(
                        None, Path(tmpfile).write_bytes, resp.result
                    )

            # cached movie is complete, update the timestamp so it's not flushed
            mtime: float = os.stat(tmpfile).st_mtime
            os.utime(tmpfile, (time(), mtime))
            await StaticFileHandler.get(self, tmpfile, include_body=include_body)
            return None

        else:  # assuming simple mjpeg camera
            raise HTTPError(400, 'unknown operation')

    def on_finish(self):
        # delete any cached file older than an hour
        stale_time: float = time() - (60 * 60)
        try:
            for f in os.listdir(self.tmpdir):
                f = os.path.join(self.tmpdir, f)
                if os.path.isfile(f) and os.stat(f).st_atime <= stale_time:
                    os.remove(f)
        except Exception:
            logging.exception('could not delete temp file')

    def get_absolute_path(self, root, path):
        return path

    def validate_absolute_path(self, root, absolute_path):
        return absolute_path


class MovieDownloadHandler(MoviePlaybackHandler):
    def set_extra_headers(self, filename):
        if self.get_status() in (200, 304):
            self.set_header(
                'Content-Disposition',
                'attachment; filename=' + self.pretty_filename + ';',
            )
            self.set_header('Expires', '0')
