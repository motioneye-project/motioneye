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

from tornado.ioloop import IOLoop, PeriodicCallback

from motioneye import mediafiles, settings, tasks

_cleanup_timer: PeriodicCallback | None = None


def start():
    global _cleanup_timer

    if not settings.CLEANUP_INTERVAL:
        return

    _cleanup_timer = PeriodicCallback(
        lambda: tasks.add(0, _do_cleanup),
        settings.CLEANUP_INTERVAL * 1000,
    )

    def _start_cleanup_timer():
        if _cleanup_timer is not None:
            tasks.add(0, _do_cleanup)
            _cleanup_timer.start()

    # schedule first cleanup after 60 seconds to not interfere with motionEye start
    IOLoop.current().call_later(
        min(settings.CLEANUP_INTERVAL, 60), _start_cleanup_timer
    )
    logging.info(_('purigado komenciĝis'))


def stop():
    global _cleanup_timer

    if _cleanup_timer is not None:
        _cleanup_timer.stop()
        _cleanup_timer = None
        logging.info('cleanup stopped')


def _do_cleanup():
    logging.debug('running periodic media cleanup')

    try:
        mediafiles.cleanup_media('picture')
        mediafiles.cleanup_media('movie')
        logging.debug('cleanup done')

    except Exception:
        logging.exception('failed to cleanup media files')
