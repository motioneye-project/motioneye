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
import pickle  # nosec: B403
from calendar import timegm
from datetime import datetime, timedelta
from multiprocessing import Pool
from multiprocessing.pool import Pool as PoolClass
from time import time

from tornado.ioloop import IOLoop

from motioneye import settings

_INTERVAL: int = 2
_STATE_FILE_NAME: str = 'tasks.pickle'
_MAX_TASKS: int = 100

# we must be sure there's only one extra process that handles all tasks
# TODO replace the pool with one simple thread: concurrent.futures.ThreadPoolExecutor
_POOL_SIZE: int = 1

_tasks: list[tuple] = []
_pool: PoolClass | None = None


def _init_pool_process() -> None:
    import signal

    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)


def start() -> None:
    global _pool

    _load()
    _pool = Pool(_POOL_SIZE, initializer=_init_pool_process)

    IOLoop.current().add_timeout(timedelta(seconds=_INTERVAL), _check_tasks)


def stop() -> None:
    global _pool

    # close pool gracefully, letting running tasks finish
    # but set global _pool to None to terminate handler loop
    pool: PoolClass | None = _pool
    _pool = None

    if pool is not None:
        pool.close()
        pool.join()


def add(when, func, tag: str | None = None, callback=None, **params) -> None:
    if len(_tasks) >= _MAX_TASKS:
        logging.error(f'the maximum number of tasks ({_MAX_TASKS}) has been reached')
        return

    now: float = time()

    if isinstance(when, int):  # delay, in seconds
        when += now

    elif isinstance(when, timedelta):
        when = now + when.total_seconds()

    elif isinstance(when, datetime):
        when = timegm(when.timetuple())

    i: int = 0
    while i < len(_tasks) and _tasks[i][0] <= when:
        i += 1

    logging.debug(f'adding task "{tag or func.__name__}" in {when - now} seconds')
    _tasks.insert(i, (when, func, tag, callback, params))

    _save()


def _check_tasks() -> None:
    if _pool is None:
        return

    IOLoop.current().add_timeout(timedelta(seconds=_INTERVAL), _check_tasks)

    now: float = time()
    changed: bool = False
    while _tasks and _tasks[0][0] <= now:
        _when, func, tag, callback, params = _tasks.pop(0)

        logging.debug(f'executing task "{tag or func.__name__}"')
        _pool.apply_async(
            func, kwds=params, callback=callback if callable(callback) else None
        )

        changed = True

    if changed:
        _save()


def _load() -> None:
    global _tasks

    _tasks = []

    file_path: str = os.path.join(settings.CONF_PATH, _STATE_FILE_NAME)

    if os.path.exists(file_path):
        logging.debug(f'loading tasks from "{file_path}"...')

        try:
            f = open(file_path, 'rb')  # noqa: SIM115

        except Exception as e:
            logging.error(f'could not open tasks file "{file_path}": {e}')
            return

        try:
            _tasks = pickle.load(f)  # nosec: B301

        except Exception as e:
            logging.error(f'could not read tasks from file "{file_path}": {e}')

        finally:
            f.close()


def _save() -> None:
    file_path: str = os.path.join(settings.CONF_PATH, _STATE_FILE_NAME)

    logging.debug(f'saving tasks to "{file_path}"...')

    try:
        f = open(file_path, 'wb')  # noqa: SIM115

    except Exception as e:
        logging.error(f'could not open tasks file "{file_path}": {e}')
        return

    try:
        # don't save tasks that have a callback
        tasks: list = [t for t in _tasks if not t[3]]
        pickle.dump(tasks, f)

    except Exception as e:
        logging.error(f'could not save tasks to file "{file_path}": {e}')

    finally:
        f.close()
