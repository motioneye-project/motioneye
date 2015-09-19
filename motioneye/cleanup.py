
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
import logging
import multiprocessing
import os
import signal
import tornado

import mediafiles
import settings
import thumbnailer


_process = None


def start():
    if not settings.CLEANUP_INTERVAL:
        return

    # schedule the first call a bit later to improve performance at startup
    ioloop = tornado.ioloop.IOLoop.instance()
    ioloop.add_timeout(datetime.timedelta(seconds=min(settings.CLEANUP_INTERVAL, 60)), _run_process)


def stop():
    global _process
    
    if not running():
        _process = None
        return
    
    if _process.is_alive():
        _process.join(timeout=10)
    
    if _process.is_alive():
        logging.error('cleanup process did not finish in time, killing it...')
        os.kill(_process.pid, signal.SIGKILL)
    
    _process = None


def running():
    return _process is not None and _process.is_alive()


def _run_process():
    global _process
    
    ioloop = tornado.ioloop.IOLoop.instance()
    
    if thumbnailer.running():
        # postpone if thumbnailer is currently running
        ioloop.add_timeout(datetime.timedelta(seconds=60), _run_process)
        
        return
        
    else:
        # schedule the next call
        ioloop.add_timeout(datetime.timedelta(seconds=settings.CLEANUP_INTERVAL), _run_process)

    if not running(): # check that the previous process has finished
        logging.debug('running cleanup process...')

        _process = multiprocessing.Process(target=_do_cleanup)
        _process.start()


def _do_cleanup():
    # this will be executed in a separate subprocess
    
    # ignore the terminate and interrupt signals in this subprocess
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    
    try:
        mediafiles.cleanup_media('picture')
        mediafiles.cleanup_media('movie')
        logging.debug('cleanup done')
         
    except Exception as e:
        logging.error('failed to cleanup media files: %(msg)s' % {
                'msg': unicode(e)}, exc_info=True)
