
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

import calendar
import cPickle
import datetime
import logging
import multiprocessing
import os
import time

from tornado.ioloop import IOLoop

import settings


_INTERVAL = 2
_STATE_FILE_NAME = 'tasks.pickle'
_MAX_TASKS = 100

# we must be sure there's only one extra process that handles all tasks
_POOL_SIZE = 1

_tasks = []
_pool = None


def start():
    global _pool

    io_loop = IOLoop.instance()
    io_loop.add_timeout(datetime.timedelta(seconds=_INTERVAL), _check_tasks)
    
    def init_pool_process():
        import signal

        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)

    _load()
    _pool = multiprocessing.Pool(_POOL_SIZE, initializer=init_pool_process)


def stop():
    global _pool
    
    #_pool.terminate()
    _pool = None


def add(when, func, tag=None, callback=None, **params):
    if len(_tasks) >= _MAX_TASKS:
        return logging.error('the maximum number of tasks (%d) has been reached' % _MAX_TASKS)
    
    now = time.time()
    
    if isinstance(when, int): # delay, in seconds
        when += now
        
    elif isinstance(when, datetime.timedelta):
        when = now + when.total_seconds()
        
    elif isinstance(when, datetime.datetime):
        when = calendar.timegm(when.timetuple())

    i = 0
    while i < len(_tasks) and _tasks[i][0] <= when:
        i += 1

    logging.debug('adding task "%s" in %d seconds' % (tag or func.func_name, when - now))
    _tasks.insert(i, (when, func, tag, callback, params))

    _save()


def _check_tasks():
    io_loop = IOLoop.instance()
    io_loop.add_timeout(datetime.timedelta(seconds=_INTERVAL), _check_tasks)
    
    now = time.time()
    changed = False
    while _tasks and _tasks[0][0] <= now:
        (when, func, tag, callback, params) = _tasks.pop(0)  # @UnusedVariable
        
        logging.debug('executing task "%s"' % tag or func.func_name)
        _pool.apply_async(func, kwds=params, callback=callback if callable(callback) else None)

        changed = True
    
    if changed:
        _save()


def _load():
    global _tasks
    
    _tasks = []

    file_path = os.path.join(settings.CONF_PATH, _STATE_FILE_NAME)
    
    if os.path.exists(file_path):
        logging.debug('loading tasks from "%s"...' % file_path)
    
        try:
            file = open(file_path, 'r')
        
        except Exception as e:
            logging.error('could not open tasks file "%s": %s' % (file_path, e))
            
            return
        
        try:
            _tasks = cPickle.load(file)

        except Exception as e:
            logging.error('could not read tasks from file "%s": %s' % (file_path, e))

        finally:
            file.close()
            

def _save():
    file_path = os.path.join(settings.CONF_PATH, _STATE_FILE_NAME)

    logging.debug('saving tasks to "%s"...' % file_path)

    try:
        file = open(file_path, 'w')

    except Exception as e:
        logging.error('could not open tasks file "%s": %s' % (file_path, e))
        
        return

    try:
        # don't save tasks that have a callback
        tasks = [t for t in _tasks if not t[3]]
        cPickle.dump(tasks, file)

    except Exception as e:
        logging.error('could not save tasks to file "%s": %s'% (file_path, e))

    finally:
        file.close()
