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

import fcntl
import functools
import logging
import multiprocessing
import os.path
import re
import subprocess
from collections import deque
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import datetime, timedelta
from errno import EAGAIN, ENOENT
from hashlib import sha1
from io import BytesIO
from multiprocessing.reduction import ForkingPickler
from select import PIPE_BUF
from signal import SIGKILL, SIGTERM
from time import time
from typing import Any
from zipfile import ZipFile

from PIL import Image
from tornado.concurrent import Future
from tornado.ioloop import IOLoop

from motioneye import config, settings, uploadservices, utils
from motioneye.utils.dtconv import pretty_date_time

_PICTURE_EXTS = ['.jpg']
_MOVIE_EXTS = ['.avi', '.mp4', '.mov', '.swf', '.flv', '.mkv', '.mpg']

# entries per message from the listing subprocess: one per file made the child wait
# for the parent at every pipe buffer, the whole list at once costs it the memory
_LIST_CHUNK = 32
# a message has to fit one pipe write of PIPE_BUF bytes, which is atomic: the parent
# then never finds a part of a message in the pipe, to wait for the rest of it
# (4 bytes are the length that multiprocessing puts in front)
_LIST_MESSAGE_MAX = PIPE_BUF - 4

FFMPEG_CODEC_MAPPING = {
    'mpeg4': 'mpeg4',
    'msmpeg4': 'msmpeg4v2',
    'swf': 'flv1',
    'flv': 'flv1',
    'mov': 'mpeg4',
    'mp4': 'h264',
    'mkv': 'h264',
    'mp4:h264_omx': 'h264_omx',
    'mkv:h264_omx': 'h264_omx',
    'mp4:h264_v4l2m2m': 'h264_v4l2m2m',
    'mkv:h264_v4l2m2m': 'h264_v4l2m2m',
    'hevc': 'hevc',
}

FFMPEG_FORMAT_MAPPING = {
    'mpeg4': 'avi',
    'msmpeg4': 'avi',
    'swf': 'swf',
    'flv': 'flv',
    'mov': 'mov',
    'mp4': 'mp4',
    'mkv': 'matroska',
    'mp4:h264_omx': 'mp4',
    'mkv:h264_omx': 'matroska',
    'mp4:h264_v4l2m2m': 'mp4',
    'mkv:h264_v4l2m2m': 'matroska',
    'hevc': 'mp4',
}

FFMPEG_EXT_MAPPING = {
    'mpeg4': 'avi',
    'msmpeg4': 'avi',
    'swf': 'swf',
    'flv': 'flv',
    'mov': 'mov',
    'mp4': 'mp4',
    'mkv': 'mkv',
    'mp4:h264_omx': 'mp4',
    'mkv:h264_omx': 'mkv',
    'mp4:h264_v4l2m2m': 'mp4',
    'mkv:h264_v4l2m2m': 'mkv',
    'hevc': 'mp4',
}

MOVIE_EXT_TYPE_MAPPING = {
    'avi': 'video/x-msvideo',
    'mp4': 'video/mp4',
    'mov': 'video/quicktime',
    'swf': 'application/x-shockwave-flash',
    'flv': 'video/x-flv',
    'mkv': 'video/x-matroska',
    'mpg': 'video/mpeg',
}

# a cache of prepared files (whose preparing time is significant)
_prepared_files: dict = {}

_timelapse_process: Any = None
_timelapse_data = None

_ffmpeg_binary_cache = None


def _list_media_files(
    base_path: str,
    exts: list[str],
    sub_path: str | None = None,
    with_stat: bool = True,
    *,
    min_timestamp: float | None = None,
    max_timestamp: float | None = None,
) -> list[tuple]:
    # Determine scan path based on sub_path parameter
    if sub_path is not None:
        if sub_path == 'ungrouped':
            sub_path = ''

        scan_path = os.path.join(base_path, sub_path)
        if not os.path.exists(scan_path):
            return []
    else:
        scan_path = base_path

    # loop-invariant: only compute the window flag once
    windowed: bool = min_timestamp is not None or max_timestamp is not None

    media_files = []
    for entry in os.scandir(scan_path):
        # ignore hidden files/dirs and other unwanted files
        if entry.name.startswith('.') or entry.name == 'lastsnap.jpg':
            continue

        # check if it's a file first (most common case)
        if entry.is_file(follow_symlinks=False):
            # filter by extension before calling stat
            if not any(entry.path.lower().endswith(e) for e in exts):
                continue

            # If stat is not needed, use None as placeholder
            st = None
            if with_stat or windowed:
                # stat call may fail due to race conditions or permission issues
                try:
                    st = entry.stat(follow_symlinks=False)
                except Exception as e:
                    logging.error(f'stat failed: {e}')
                    continue

                # Skip files outside the caller's window before any of the
                # expensive per-file work in _do_list_media. Bounds are
                # inclusive, i.e. wider than any caller's own filter.
                if windowed:
                    mtime: float = st.st_mtime
                    if min_timestamp is not None and mtime < min_timestamp:
                        continue
                    if max_timestamp is not None and mtime > max_timestamp:
                        continue

            media_files.append((entry.path, st if with_stat else None))

        # recurse into subdirectories only when no sub_path filter is set
        elif sub_path is None and entry.is_dir(follow_symlinks=False):
            media_files.extend(
                _list_media_files(
                    entry.path,
                    exts,
                    with_stat=with_stat,
                    min_timestamp=min_timestamp,
                    max_timestamp=max_timestamp,
                )
            )

    return media_files


def _remove_empty_dirs(dir_path: str, target_dir: str) -> int:
    # removes the directory, then its parents as long as they are empty, but unlike
    # os.removedirs() never the target dir itself or anything above it
    dir_path = os.path.normpath(dir_path)
    target_dir = os.path.normpath(target_dir)
    if os.path.commonpath([dir_path, target_dir]) != target_dir:
        return 0

    count: int = 0
    while dir_path != target_dir:
        try:
            os.rmdir(dir_path)
            count += 1

        except OSError:
            break  # not empty

        dir_path = os.path.dirname(dir_path)

    return count


def _remove_older_files(
    directory: str,
    moment: datetime,
    clean_cloud_info: dict,
    exts: list[str],
):
    removed_folder_count = 0
    dir_paths = set()
    for full_path, st in _list_media_files(directory, exts, with_stat=True):
        try:
            file_moment = datetime.fromtimestamp(st.st_mtime)

        except Exception as e:  # e.g. a time out of range for this platform
            logging.error(f'failed to check {full_path}: {e}')
            continue

        if file_moment < moment:
            logging.debug(f'removing file {full_path}...')

            # remove the file itself
            try:
                os.remove(full_path)

            except OSError as e:
                if e.errno == ENOENT:
                    pass  # the file might have been removed in the meantime

                else:
                    logging.error(f'failed to remove {full_path}: {e}')

            dir_paths.add(os.path.dirname(full_path))

    # remove the parent directories if empty or contain only thumb files; check
    # each once, subfolders before their parents
    for dir_path in sorted(dir_paths, key=len, reverse=True):
        if not os.path.exists(dir_path):
            continue

        try:
            listing = os.listdir(dir_path)

        except Exception as e:
            logging.error(f'failed to list {dir_path}: {e}')
            continue

        thumbs = [line for line in listing if line.endswith('.thumb')]

        if len(listing) == len(thumbs):  # only thumbs
            for p in thumbs:
                try:
                    os.remove(os.path.join(dir_path, p))

                except Exception as e:
                    logging.error(f'failed to remove {p}: {e}')

        if not listing or len(listing) == len(thumbs):
            logging.debug(f'removing empty directory {dir_path}...')
            try:
                removed_folder_count += _remove_empty_dirs(dir_path, directory)

            except Exception as e:
                logging.error(f'failed to remove {dir_path}: {e}')

    if clean_cloud_info and removed_folder_count > 0:
        uploadservices.clean_cloud(directory, {}, clean_cloud_info)


def _send_entries(pipe, entries: list[dict]) -> None:
    """Send the entries as one message, or in halves while that is too big for one
    atomic pipe write. Only a single entry bigger than that, with a path of some
    kB, is sent as it is."""
    data = ForkingPickler.dumps(entries)  # as pipe.send() does
    if len(data) > _LIST_MESSAGE_MAX and len(entries) > 1:
        half = len(entries) // 2
        _send_entries(pipe, entries[:half])
        _send_entries(pipe, entries[half:])
        return

    pipe.send_bytes(data)


def _do_list_media(
    pipe,
    target_dir: str,
    exts: list[str],
    sub_path: str | None = None,
    with_stat: bool = True,
    min_timestamp: float | None = None,
    max_timestamp: float | None = None,
) -> None:
    from mimetypes import guess_type

    mf = _list_media_files(
        target_dir,
        exts,
        sub_path,
        with_stat,
        min_timestamp=min_timestamp,
        max_timestamp=max_timestamp,
    )
    mime_types: dict[str, str] = {}  # by extension: the same for thousands of files
    chunk: list[dict] = []
    for p, st in mf:
        path = p[len(target_dir) :]
        if not path.startswith('/'):
            path = '/' + path

        if with_stat and st is not None:
            timestamp = st.st_mtime
            size = st.st_size
            ext = os.path.splitext(path)[1].lower()
            if ext not in mime_types:
                mime_types[ext] = guess_type(path)[0] or 'video/mpeg'

            moment = datetime.fromtimestamp(timestamp)
            chunk.append(
                {
                    'path': path,
                    'mimeType': mime_types[ext],
                    'momentStr': pretty_date_time(moment),
                    'momentStrShort': pretty_date_time(moment, short=True),
                    'sizeStr': utils.pretty_size(size),
                    'timestamp': timestamp,
                }
            )
        else:
            # When stat is not available, only send the path
            chunk.append({'path': path})

        if len(chunk) >= _LIST_CHUNK:
            _send_entries(pipe, chunk)
            chunk = []

    if chunk:
        _send_entries(pipe, chunk)

    pipe.close()


def _do_zip(pipe, target_dir, exts, sub_path, working):
    mf = _list_media_files(target_dir, exts, sub_path, with_stat=False)
    paths = []
    for p, st in mf:  # st will be None when with_stat=False
        paths.append(p[len(target_dir) :].removeprefix('/'))

    zip_filename = os.path.join(settings.MEDIA_PATH, f'.zip-{int(time())}')
    logging.debug(f'adding {len(paths)} files to zip file "{zip_filename}"')

    try:
        with ZipFile(zip_filename, mode='w') as f:
            for path in paths:
                full_path = os.path.join(target_dir, path)
                f.write(full_path, path)

    except Exception as e:
        logging.error(f'failed to create zip file "{zip_filename}": {e}')

        working.value = False
        pipe.close()
        return

    logging.debug(f'reading zip file "{zip_filename}" into memory')

    try:
        with open(zip_filename, mode='rb') as f:
            data = f.read()

        working.value = False
        pipe.send(data)
        logging.debug('zip data ready')

    except Exception as e:
        logging.error(f'failed to read zip file "{zip_filename}": {e}')
        working.value = False

    finally:
        os.remove(zip_filename)
        pipe.close()


def _do_list_pictures(pipe, target_dir, sub_path):
    mf = _list_media_files(target_dir, _PICTURE_EXTS, sub_path, with_stat=True)
    for p, st in mf:
        timestamp = st.st_mtime

        pipe.send({'path': p, 'timestamp': timestamp})

    pipe.close()


def find_ffmpeg() -> tuple:
    global _ffmpeg_binary_cache
    if _ffmpeg_binary_cache:
        return _ffmpeg_binary_cache

    # binary
    try:
        binary = utils.call_subprocess(['which', 'ffmpeg'])

    except subprocess.CalledProcessError:  # not found
        return None, None, None

    # version
    try:
        output = utils.call_subprocess([binary, '-version'])

    except subprocess.CalledProcessError as e:
        logging.error(f'ffmpeg: could not find version: {e}')
        return None, None, None

    result = re.findall('ffmpeg version (.+?) ', output, re.IGNORECASE)
    version = result and result[0] or ''

    # codecs
    try:
        output = utils.call_subprocess([binary, '-codecs', '-hide_banner'])

    except subprocess.CalledProcessError as e:
        logging.error(f'ffmpeg: could not list supported codecs: {e}')
        return None, None, None

    lines = output.split('\n')
    lines = [line for line in lines if re.match('^ [DEVILSA.]{6} [^=].*', line)]

    codecs = {}
    for line in lines:
        m = re.match(r'^ [DEVILSA.]{6} ([\w+_]+)', line)
        if not m:
            continue

        codec = m.group(1)

        decoders = set()
        encoders = set()

        m = re.search(r'decoders: ([\w\s_]+)+', line)
        if m:
            decoders = set(m.group(1).split())

        m = re.search(r'encoders: ([\w\s_]+)+', line)
        if m:
            encoders = set(m.group(1).split())

        codecs[codec] = {'encoders': encoders, 'decoders': decoders}

    logging.debug(f'found ffmpeg executable "{binary}" version "{version}"')

    _ffmpeg_binary_cache = (binary, version, codecs)

    return _ffmpeg_binary_cache


def cleanup_media(media_type: str) -> None:
    logging.debug(f'cleaning up {media_type}s...')

    if media_type == 'picture':
        exts = _PICTURE_EXTS

    else:  # media_type == 'movie'
        exts = _MOVIE_EXTS + ['.thumb']

    for camera_id in config.get_camera_ids():
        camera_config: dict = config.get_camera(camera_id)
        if not utils.is_local_motion_camera(camera_config):
            continue

        preserve_media = camera_config.get(f'@preserve_{media_type}s', 0)
        if preserve_media == 0:
            continue  # preserve forever

        still_images_enabled = bool(camera_config['picture_filename']) or bool(
            camera_config['snapshot_filename']
        )
        movies_enabled = bool(camera_config['movie_output'])

        if media_type == 'picture' and not still_images_enabled:
            continue  # only cleanup pictures for cameras with still images enabled

        if media_type == 'movie' and not movies_enabled:
            continue  # only cleanup movies for cameras with movies enabled

        preserve_moment = datetime.now() - timedelta(days=preserve_media)

        target_dir: str = camera_config['target_dir']
        cloud_enabled = camera_config.get('@upload_enabled')
        clean_cloud_enabled = camera_config.get('@clean_cloud_enabled')
        cloud_dir = camera_config.get('@upload_location')
        service_name = camera_config.get('@upload_service')
        clean_cloud_info = None
        if (
            cloud_enabled
            and clean_cloud_enabled
            # when files are removed right after upload, the local folders are
            # the source of truth no longer, so cloud cleanup must be skipped to
            # avoid deleting the just-uploaded copies (see #3089)
            and not camera_config.get('@clean_uploaded')
            and camera_id
            and service_name
            and cloud_dir
        ):
            clean_cloud_info = {
                'camera_id': camera_id,
                'service_name': service_name,
                'cloud_dir': cloud_dir,
            }
        logging.debug(
            f'calling _remove_older_files: {cloud_enabled} {clean_cloud_enabled} {clean_cloud_info}'
        )
        _remove_older_files(
            target_dir, preserve_moment, clean_cloud_info or {}, exts=exts
        )


def get_movie_duration_seconds(path: str) -> int:
    cmd = [
        'ffprobe',
        '-v',
        'error',
        '-show_entries',
        'format=duration',
        '-of',
        'default=noprint_wrappers=1:nokey=1',
        path,
    ]

    try:
        result = utils.call_subprocess(cmd, stderr=None)
        return int(float(result))

    except Exception as e:
        logging.error(f'failed to determine duration of {path}: {e}')
        return 0


def make_movie_preview(camera_config: dict, rel_path: str) -> str | None:
    target_dir: str = camera_config['target_dir']
    utils.validate_paths(rel_path, target_dir=target_dir)
    full_path = os.path.join(target_dir, rel_path)

    framerate = camera_config['framerate']
    pre_capture = camera_config['pre_capture']
    offs = pre_capture / framerate
    movie_duration = get_movie_duration_seconds(full_path)
    offs = max(
        (x for x in {offs * 2, offs} if x <= movie_duration), default=movie_duration / 2
    )
    thumb_path: str = full_path + '.thumb'

    logging.debug(
        f'creating movie preview for {full_path} with an offset of {offs} seconds...'
    )

    cmd: list = [
        'ffmpeg',
        '-i',
        full_path,
        '-f',
        'mjpeg',
        '-vframes',
        '1',
        '-ss',
        str(offs),
        '-y',
        thumb_path,
    ]
    logging.debug(f'running command {cmd}')

    try:
        utils.call_subprocess(cmd, stderr=subprocess.STDOUT)

    except subprocess.CalledProcessError as e:
        logging.error(f'failed to create movie preview for {full_path}: {e}')

        return None

    try:
        st = os.stat(thumb_path)

    except OSError:
        logging.error(f'failed to create movie preview for {full_path}')

        return None

    if st.st_size == 0:
        logging.debug(
            f'movie probably too short, grabbing first frame from {full_path}...'
        )

        cmd = [
            'ffmpeg',
            '-i',
            full_path,
            '-f',
            'mjpeg',
            '-vframes',
            '1',
            '-ss',
            '0',
            '-y',
            thumb_path,
        ]
        logging.debug(f'running command {cmd}')

        # try again, this time grabbing the very first frame
        try:
            utils.call_subprocess(cmd, stderr=subprocess.STDOUT)

        except subprocess.CalledProcessError as e:
            logging.error(f'failed to create movie preview for {full_path}: {e}')

            return None

        try:
            st = os.stat(thumb_path)

        except OSError:
            logging.error(f'failed to create movie preview for {full_path}')

            return None

    if st.st_size == 0:
        logging.error(f'failed to create movie preview for {full_path}')
        with suppress(Exception):  # nothing we can do about it
            os.remove(thumb_path)

        return None

    return thumb_path


def list_media(
    camera_config: dict,
    media_type: str,
    prefix: str | None = None,
    with_stat: bool = True,
    *,
    min_timestamp: float | None = None,
    max_timestamp: float | None = None,
) -> Awaitable:
    target_dir: str = camera_config['target_dir']
    utils.validate_paths(prefix, target_dir=target_dir)

    if media_type == 'picture':
        exts = _PICTURE_EXTS

    elif media_type == 'movie':
        exts = _MOVIE_EXTS

    fut: Future = Future()

    def start() -> None:
        media_list: list = []

        def finish(result) -> None:
            global _listings_running
            _listings_running -= 1
            # on the loop, not here: a chain of failing starts would recurse
            IOLoop.current().add_callback(_start_next_listing)
            if not fut.done():
                fut.set_result(result)

        logging.debug('starting media listing subprocess...')
        try:
            parent_pipe, child_pipe = multiprocessing.Pipe(duplex=False)
            process = multiprocessing.Process(
                target=_do_list_media,
                args=(
                    child_pipe,
                    target_dir,
                    exts,
                    prefix,
                    with_stat,
                    min_timestamp,
                    max_timestamp,
                ),
            )
            process.start()
            child_pipe.close()

        except Exception as e:  # e.g. the fork itself fails for lack of memory
            logging.error(f'could not start the media listing process: {e}')
            finish(None)
            return

        # read the pipe as the child fills it; the child's exit closes the pipe
        loop = IOLoop.current()
        fd = parent_pipe.fileno()

        def done(result) -> None:
            loop.remove_handler(fd)
            loop.remove_timeout(timeout_handle)
            parent_pipe.close()
            finish(result)

        def on_readable(fd, events) -> None:
            try:
                while parent_pipe.poll():
                    media_list.extend(parent_pipe.recv())

            except (EOFError, OSError):  # finished, or killed, e.g. for lack of memory
                process.join()
                if process.exitcode != 0:
                    logging.error(
                        f'media listing process ended with code {process.exitcode}'
                    )
                    done(None)  # a partial list is no list, like after a timeout
                    return

                logging.debug(
                    f'media listing process has returned {len(media_list)} files'
                )
                done(media_list)

        def on_timeout() -> None:
            logging.error('timeout waiting for the media listing process to finish')
            with suppress(Exception):  # nevermind
                if process.pid is not None:
                    os.kill(process.pid, SIGKILL)

            done(None)

        timeout_handle = loop.call_later(settings.LIST_MEDIA_TIMEOUT, on_timeout)
        loop.add_handler(fd, on_readable, IOLoop.READ)

    def give_up() -> None:
        # still waiting after a whole timeout: answer like a timed-out listing
        # rather than start one that the caller has given up on by now
        if start in _listings_waiting:
            _listings_waiting.remove(start)
            logging.error('timeout waiting for a media listing slot')
            if not fut.done():
                fut.set_result(None)

    _listings_waiting.append(start)
    _start_next_listing()
    if start in _listings_waiting:
        logging.debug(
            f'media listing waits for a slot, {_listings_running} running, '
            f'{len(_listings_waiting)} waiting'
        )
        IOLoop.current().call_later(settings.LIST_MEDIA_TIMEOUT, give_up)

    return fut


# Each listing forks the whole server, so a burst of requests, e.g. a media
# browser opening every camera at once, could exhaust the memory. At most
# LIST_MEDIA_MAX_PARALLEL listings run at a time; the others wait their turn,
# for one timeout at most, and the timeout of a listing counts from when it
# actually starts.
_listings_running: int = 0
_listings_waiting: deque[Callable[[], None]] = deque()


def _start_next_listing() -> None:
    global _listings_running
    limit = max(1, settings.LIST_MEDIA_MAX_PARALLEL)
    while _listings_waiting and _listings_running < limit:
        _listings_running += 1
        _listings_waiting.popleft()()


def get_media_path(camera_config: dict, path: str):
    target_dir: str = camera_config['target_dir']
    utils.validate_paths(path, target_dir=target_dir)
    full_path: str = os.path.join(target_dir, path)
    return full_path


def get_media_content(camera_config: dict, path: str):
    target_dir: str = camera_config['target_dir']
    utils.validate_paths(path, target_dir=target_dir)
    full_path: str = os.path.join(target_dir, path)

    try:
        with open(full_path, 'rb') as f:
            return f.read()

    except Exception as e:
        logging.error(f'failed to read file {full_path}: {e}')
        return None


def get_zipped_content(camera_config: dict, media_type: str, group: str) -> Awaitable:
    target_dir: str = camera_config['target_dir']
    utils.validate_paths(group, target_dir=target_dir)

    if media_type == 'picture':
        exts = _PICTURE_EXTS

    elif media_type == 'movie':
        exts = _MOVIE_EXTS

    working = multiprocessing.Value('b')
    working.value = True

    logging.debug('starting zip subprocess...')

    parent_pipe, child_pipe = multiprocessing.Pipe(duplex=False)
    process = multiprocessing.Process(
        target=_do_zip, args=(child_pipe, target_dir, exts, group, working)
    )
    process.start()
    child_pipe.close()

    # poll the subprocess to see when it has finished
    started = datetime.now()

    def poll_process():
        if working.value:
            now = datetime.now()
            delta = now - started
            if delta.seconds < settings.ZIP_TIMEOUT:
                IOLoop.current().call_later(0.5, poll_process)

            else:  # process did not finish in time
                logging.error('timeout waiting for the zip process to finish')
                with suppress(Exception):  # nevermind
                    os.kill(process.pid, SIGTERM)

                fut.set_result(None)

        else:  # finished
            try:
                data = parent_pipe.recv()
                logging.debug(f'zip process has returned {len(data)} bytes')

            except Exception:
                data = None

            fut.set_result(data)

    fut: Future = Future()
    poll_process()
    return fut


def make_timelapse_movie(camera_config, framerate, interval, group: str):
    global _timelapse_process
    global _timelapse_data

    target_dir: str = camera_config['target_dir']
    utils.validate_paths(group, target_dir=target_dir)
    # save movie_codec as a different variable so it doesn't get lost in the CODEC_MAPPING
    movie_codec = camera_config.get('movie_codec')

    codec = FFMPEG_CODEC_MAPPING.get(movie_codec, movie_codec)
    fmt = FFMPEG_FORMAT_MAPPING.get(movie_codec, movie_codec)
    file_format = FFMPEG_EXT_MAPPING.get(movie_codec, movie_codec)

    logging.debug('starting picture listing subprocess...')

    parent_pipe, child_pipe = multiprocessing.Pipe(duplex=False)
    _timelapse_process = multiprocessing.Process(
        target=_do_list_pictures, args=(child_pipe, target_dir, group)
    )
    _timelapse_process.progress = 0
    _timelapse_process.start()
    _timelapse_data = None

    child_pipe.close()

    started = [datetime.now()]
    media_list = []

    # use correct extension for the movie_codec
    tmp_filename: str = os.path.join(
        settings.MEDIA_PATH, f'.{int(time())}.{file_format}'
    )

    def read_media_list():
        while parent_pipe.poll():
            try:
                media_list.append(parent_pipe.recv())

            except EOFError:
                break

    def poll_media_list_process():
        if _timelapse_process.is_alive():  # not finished yet
            now = datetime.now()
            delta = now - started[0]
            # the subprocess has limited time to complete its job
            if delta.seconds < settings.TIMELAPSE_TIMEOUT:
                IOLoop.current().call_later(0.5, poll_media_list_process)
                read_media_list()

            else:  # process did not finish in time
                logging.error('timeout waiting for the media listing process to finish')
                with suppress(Exception):  # nevermind
                    os.kill(_timelapse_process.pid, SIGTERM)

                _timelapse_process.progress = -1

        else:  # finished
            read_media_list()
            logging.debug(f'media listing process has returned {len(media_list)} files')

            if not media_list:
                _timelapse_process.progress = -1

                return

            pictures: list = select_pictures(media_list)
            make_movie(pictures)

    def select_pictures(media_list: list) -> list:
        media_list.sort(key=lambda e: e['timestamp'])
        start = media_list[0]['timestamp']
        slices: dict = {}
        max_idx = 0
        for m in media_list:
            offs = m['timestamp'] - start
            pos = float(offs) / interval - 0.5
            idx = round(pos)
            max_idx = idx
            m['delta'] = abs(pos - idx)
            slices.setdefault(idx, []).append(m)

        selected = []
        for i in range(max_idx + 1):
            s = slices.get(i)
            if not s:
                continue

            selected.append(min(s, key=lambda m: m['delta']))

        logging.debug(f'selected {len(selected)}/{len(media_list)} media files')

        return selected

    def make_movie(pictures: list) -> None:
        global _timelapse_process

        # don't specify file format with -f, let ffmpeg work it out from the extension
        cmd: list = [
            'ffmpeg',
            '-r',
            str(framerate),
            '-f',
            'concat',
            '-protocol_whitelist',
            'fd,file,pipe',
            '-safe',
            '0',
            '-i',
            '-',
            '-y',
            '-vcodec',
            codec,
            '-format',
            fmt,
            '-b:v',
            '9999999',
            '-qscale:v',
            '0.1',
            tmp_filename,
        ]

        logging.debug(f'running command {cmd}')

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
            )

        except OSError as e:
            logging.error(f'failed to start ffmpeg: {e}')
            # end the timelapse, or every next one is refused as already running
            _timelapse_process.progress = -1

            return

        _timelapse_process = process
        _timelapse_process.progress = 0.01  # 1%

        for p in pictures:
            path: str = p['path'].replace("'", "'\\''")
            _timelapse_process.stdin.write(f"file 'file:{path}'\n".encode())
        _timelapse_process.stdin.close()

        # make subprocess stdout pipe non-blocking
        fd = _timelapse_process.stdout.fileno()
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        _poll_movie_process(pictures, [])

    def _poll_movie_process(pictures: list, output: list):
        global _timelapse_process
        global _timelapse_data
        output_chunk: bytes = b''

        if _timelapse_process.poll() is None:  # not finished yet
            # Read output chunk from process pipe
            try:
                output_chunk = os.read(_timelapse_process.stdout.fileno(), 65536)

            except OSError as e:
                if e.errno == EAGAIN:  # no data available right now
                    output_chunk = b''
                else:
                    raise

            # Append output chunk to full output list and increment progress value
            if output_chunk:
                output.append(output_chunk)

                frames: list = re.findall(rb'frame=\s*(\d+)', output_chunk)
                if frames:
                    frame_index: int = int(frames[-1])
                    _timelapse_process.progress = max(0.01, frame_index / len(pictures))

                    logging.debug(
                        f'timelapse progress: {int(100 * _timelapse_process.progress)} %'
                    )

            # Schedule next iteration
            IOLoop.current().call_later(
                0.5,
                functools.partial(_poll_movie_process, pictures, output),
            )

        else:  # finished
            exit_code = _timelapse_process.poll()
            # Read all remaining output from process pipe
            try:
                while True:
                    try:
                        output_chunk = os.read(
                            _timelapse_process.stdout.fileno(), 65536
                        )
                        if not output_chunk:
                            break

                    except OSError as e:
                        if e.errno == EAGAIN:
                            break

                        raise

                    output.append(output_chunk)

            finally:
                _timelapse_process = None

            if exit_code != 0:
                logging.error(
                    'ffmpeg process failed (exit code %s):\n%s',
                    exit_code,
                    b''.join(output).decode(errors='replace'),
                )
                _timelapse_data = None

                with suppress(Exception):  # nothing we can do about it
                    os.remove(tmp_filename)

            else:
                logging.debug(
                    f'reading timelapse movie file "{tmp_filename}" into memory'
                )

                try:
                    with open(tmp_filename, mode='rb') as f:
                        _timelapse_data = f.read()

                    logging.debug(
                        f'timelapse movie process has returned {len(_timelapse_data)} bytes'
                    )

                except Exception as e:
                    logging.error(
                        f'failed to read timelapse movie file "{tmp_filename}": {e}'
                    )

                finally:
                    with suppress(Exception):  # nothing we can do about it
                        os.remove(tmp_filename)

    poll_media_list_process()


def check_timelapse_movie():
    if _timelapse_process:
        if (
            hasattr(_timelapse_process, 'poll') and _timelapse_process.poll() is None
        ) or (
            hasattr(_timelapse_process, 'is_alive') and _timelapse_process.is_alive()
        ):
            return {'progress': _timelapse_process.progress, 'data': None}

        return {'progress': _timelapse_process.progress, 'data': _timelapse_data}

    return {'progress': -1, 'data': _timelapse_data}


def get_media_preview(
    camera_config: dict,
    path: str,
    media_type: str,
    width: str | None = None,
    height: str | None = None,
) -> bytes | None:
    target_dir: str = camera_config['target_dir']
    utils.validate_paths(path, target_dir=target_dir)
    full_path: str = os.path.join(target_dir, path)

    if media_type == 'movie':
        # at this point we expect the thumb to
        # have already been created by the thumbnailer task;
        # if, for some reason that's not the case,
        # we create it right away
        if not os.path.exists(full_path + '.thumb') and not make_movie_preview(
            camera_config, path
        ):
            return None

        full_path += '.thumb'

    try:
        with open(full_path, 'rb') as f:
            content = f.read()

    except Exception as e:
        logging.error(f'failed to read file {full_path}: {e}')
        return None

    if width is height is None:
        return content

    bio = BytesIO(content)
    try:
        image = Image.open(bio)

    except Exception as e:
        logging.error(f'failed to open media preview image file: {e}')
        return None

    image.thumbnail(
        (
            width and float(width) or image.width,
            height and float(height) or image.height,
        )
    )

    bio = BytesIO()
    image.save(bio, format='JPEG')

    return bio.getvalue()


def del_media_content(camera_config: dict, path: str):
    target_dir: str = camera_config['target_dir']
    utils.validate_paths(path, target_dir=target_dir)
    full_path: str = os.path.join(target_dir, path)

    try:
        # remove the file itself
        os.remove(full_path)

        # remove the thumb file
        with suppress(Exception):  # thumb file may not exist
            os.remove(full_path + '.thumb')

        # remove the parent directories if empty or contains only thumb files
        dir_path = os.path.dirname(full_path)
        listing = os.listdir(dir_path)
        thumbs = [line for line in listing if line.endswith('.thumb')]

        if len(listing) == len(thumbs):  # only thumbs
            for p in thumbs:
                os.remove(os.path.join(dir_path, p))

        if not listing or len(listing) == len(thumbs):
            logging.debug(f'removing empty directory {dir_path}...')
            _remove_empty_dirs(dir_path, target_dir)

    except Exception as e:
        logging.error(f'failed to remove file {full_path}: {e}')

        raise


def del_media_group(camera_config: dict, group: str, media_type: str):
    target_dir: str = camera_config['target_dir']
    utils.validate_paths(group, target_dir=target_dir)
    full_path: str = os.path.join(target_dir, group)

    if media_type == 'picture':
        exts = _PICTURE_EXTS

    else:  # media_type == 'movie'
        exts = _MOVIE_EXTS + ['.thumb']

    mf = _list_media_files(target_dir, exts, sub_path=group, with_stat=False)
    for path, st in mf:  # st will be None when with_stat=False
        try:
            os.remove(path)

        except Exception as e:
            logging.error(f'failed to remove file {full_path}: {e}')
            raise

    # remove the group directory if empty or contains only thumb files
    listing = os.listdir(full_path)
    thumbs = [line for line in listing if line.endswith('.thumb')]

    if len(listing) == len(thumbs):  # only thumbs
        for p in thumbs:
            os.remove(os.path.join(full_path, p))

    if not listing or len(listing) == len(thumbs):
        logging.debug(f'removing empty directory {full_path}...')
        _remove_empty_dirs(full_path, target_dir)


def get_current_picture(camera_config, width, height):
    from motioneye import mjpgclient

    jpg = mjpgclient.get_jpg(camera_config['@id'])

    if jpg is None:
        return None

    if width is height is None:
        return jpg  # no server-side resize needed

    bio = BytesIO(jpg)
    try:
        image = Image.open(bio)

    except Exception as e:
        logging.error(f'failed to open media image file: {e}')
        return None

    if width and width < 1:  # given as percent
        width = int(width * image.size[0])
    if height and height < 1:  # given as percent
        height = int(height * image.size[1])

    width = width and int(width) or image.size[0]
    height = height and int(height) or image.size[1]

    webcam_resolution = camera_config['@webcam_resolution']
    max_width = image.size[0] * webcam_resolution / 100
    max_height = image.size[1] * webcam_resolution / 100

    width = min(max_width, width)
    height = min(max_height, height)

    if width >= image.size[0] and height >= image.size[1]:
        return jpg  # no enlarging of the picture on the server side

    image.thumbnail((width, height))

    bio = BytesIO()
    image.save(bio, format='JPEG')

    return bio.getvalue()


def get_prepared_cache(key):
    return _prepared_files.pop(key, None)


def set_prepared_cache(data):
    key = sha1(str(time()).encode(), usedforsecurity=False).hexdigest()

    if key in _prepared_files:
        logging.warning(f'key "{key}" already present in prepared cache')

    _prepared_files[key] = data

    def clear():
        if _prepared_files.pop(key, None) is not None:
            logging.warning(
                f'key "{key}" was still present in the prepared cache, removed'
            )

    timeout = 3600  # the user has 1 hour to download the file after creation

    IOLoop.current().call_later(timeout, clear)

    return key
