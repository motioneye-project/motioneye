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
from concurrent.futures import ThreadPoolExecutor

from tornado.ioloop import IOLoop

# Use a single thread only to avoid possible collisions. Otherwise we'd
# need to manually prevent e.g. concurrent upload service config writes.
_POOL_SIZE: int = 1
_MAX_TASKS: int = 100

_pool: ThreadPoolExecutor | None = None
_pending_tasks: int = 0


def start() -> None:
    global _pool
    _pool = ThreadPoolExecutor(max_workers=_POOL_SIZE)


def stop() -> None:
    global _pool

    # close pool gracefully, letting tasks in pool finish
    # but set global _pool to None to not add new tasks
    pool: ThreadPoolExecutor | None = _pool
    _pool = None

    if pool is not None:
        pool.shutdown(wait=True)


def add(delay: int, func, tag: str | None = None, **params) -> None:
    global _pending_tasks
    name: str = tag or func.__name__

    if _pending_tasks >= _MAX_TASKS:
        logging.error(f'skipping task {name!r}: limit of {_MAX_TASKS} tasks reached')
        return

    if delay > 0:
        logging.debug(f'adding task {name!r} in {delay} seconds')
        IOLoop.current().call_later(delay, _submit_task, func, name, params)
    else:
        _submit_task(func, name, params)

    _pending_tasks += 1


def _submit_task(func, name: str, params: dict) -> None:
    global _pending_tasks

    if _pool is None:
        _pending_tasks -= 1
        logging.error(f'skipping task {name!r}: tasks pool not ready yet/anymore')
        return

    logging.debug(f'executing task {name!r}')
    _pool.submit(func, **params).add_done_callback(_log_task_result)


def _log_task_result(future) -> None:
    global _pending_tasks
    _pending_tasks -= 1

    if not future.cancelled():
        e = future.exception()
        if e is not None:
            logging.error(
                'scheduled task failed',
                exc_info=(type(e), e, e.__traceback__),
            )
