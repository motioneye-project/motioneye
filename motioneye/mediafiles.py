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
import errno
import fcntl
import functools
import hashlib
import io
import logging
import multiprocessing
import os.path
import re
import signal
import stat
import subprocess
import time
import typing
import zipfile
from shlex import quote

from PIL import Image
from tornado.concurrent import Future
from tornado.ioloop import IOLoop

from motioneye import config, settings, uploadservices, utils
from motioneye.utils.dtconv import pretty_date_time

_PICTURE_EXTS = ['.jpg']
_MOVIE_EXTS = ['.avi', '.mp4', '.mov', '.swf', '.flv', '.mkv']

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
    'hevc': 'h265',
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
}

# a cache of prepared files (whose preparing time is significant)
_prepared_files = {}

_timelapse_process = None
_timelapse_data = None

_ffmpeg_binary_cache = None


def findfiles(path: str) -> typing.List[tuple]:
    files = []
    for name in os.listdir(path):
        # ignore hidden files/dirs and other unwanted files
        if name.startswith('.') or name == 'lastsnap.jpg':
            continue
        pathname = os.path.join(path, name)
        st = os.lstat(pathname)
        mode = st.st_mode
        if stat.S_ISDIR(mode):
            files.extend(findfiles(pathname))

        elif stat.S_ISREG(mode):
            files.append((pathname, name, st))

    return files


def _list_media_files(
    directory: str, exts: typing.List[str], prefix: str = None
) -> typing.List[tuple]:
    media_files = []

    if prefix is not None:
        if prefix == 'ungrouped':
            prefix = ''

        root = os.path.join(directory, prefix)
        if not os.path.exists(root):
            return media_files

        for name in os.listdir(root):
            # ignore hidden files/dirs and other unwanted files
            if name.startswith('.') or name == 'lastsnap.jpg':
                continue

            full_path = os.path.join(root, name)
            try:
                st = os.stat(full_path)

            except Exception as e:
                logging.error('stat failed: ' + str(e))
                continue

            if not stat.S_ISREG(st.st_mode):  # not a regular file
                continue

            full_path_lower = full_path.lower()
            if not [e for e in exts if full_path_lower.endswith(e)]:
                continue

            media_files.append((full_path, st))

    else:
        for full_path, name, st in findfiles(directory):
            full_path_lower = full_path.lower()
            if not [e for e in exts if full_path_lower.endswith(e)]:
                continue

            media_files.append((full_path, st))

    return media_files


def _remove_older_files(
    directory: str,
    moment: datetime.datetime,
    clean_cloud_info: dict,
    exts: typing.List[str],
):
    removed_folder_count = 0
    for (full_path, st) in _list_media_files(directory, exts):
        file_moment = datetime.datetime.fromtimestamp(st.st_mtime)
        if file_moment < moment:
            logging.debug(f'removing file {full_path}...')

            # remove the file itself
            try:
                os.remove(full_path)

            except OSError as e:
                if e.errno == errno.ENOENT:
                    pass  # the file might have been removed in the meantime

                else:
                    logging.error(f'failed to remove {full_path}: {e}')

            # remove the parent directories if empty or contain only thumb files
            dir_path = os.path.dirname(full_path)
            if not os.path.exists(dir_path):
                continue

            listing = os.listdir(dir_path)
            thumbs = [l for l in listing if l.endswith('.thumb')]

            if len(listing) == len(thumbs):  # only thumbs
                for p in thumbs:
                    try:
                        os.remove(os.path.join(dir_path, p))

                    except Exception as e:
                        logging.error(f'failed to remove {p}: {e}')

            if not listing or len(listing) == len(thumbs):
                # this will possibly cause following paths that are in the media files for loop
                # to be removed in advance; the os.remove call will raise ENOENT which is silently ignored
                logging.debug(f'removing empty directory {dir_path}...')
                try:
                    os.removedirs(dir_path)
                    removed_folder_count += 1

                except Exception as e:
                    logging.error(f'failed to remove {dir_path}: {e}')

    if clean_cloud_info and removed_folder_count > 0:
        uploadservices.clean_cloud(directory, {}, clean_cloud_info)


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
        output = utils.call_subprocess([quote(binary), '-version'])

    except subprocess.CalledProcessError as e:
        logging.error(f'ffmpeg: could find version: {e}')
        return None, None, None

    result = re.findall('ffmpeg version (.+?) ', output, re.IGNORECASE)
    version = result and result[0] or ''

    # codecs
    try:
        output = utils.call_subprocess(binary + ' -codecs -hide_banner', shell=True)

    except subprocess.CalledProcessError as e:
        logging.error(f'ffmpeg: could not list supported codecs: {e}')
        return None, None, None

    lines = output.split('\n')
    lines = [l for l in lines if re.match('^ [DEVILSA.]{6} [^=].*', l)]

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

    logging.debug(f'using ffmpeg version {version}')

    _ffmpeg_binary_cache = (binary, version, codecs)

    return _ffmpeg_binary_cache


def cleanup_media(media_type: str) -> None:
    logging.debug(f'cleaning up {media_type}s...')

    if media_type == 'picture':
        exts = _PICTURE_EXTS

    else:  # media_type == 'movie'
        exts = _MOVIE_EXTS + ['.thumb']

    for camera_id in config.get_camera_ids():
        camera_config = config.get_camera(camera_id)
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

        elif media_type == 'movie' and not movies_enabled:
            continue  # only cleanup movies for cameras with movies enabled

        preserve_moment = datetime.datetime.now() - datetime.timedelta(
            days=preserve_media
        )

        target_dir = camera_config.get('target_dir')
        cloud_enabled = camera_config.get('@upload_enabled')
        clean_cloud_enabled = camera_config.get('@clean_cloud_enabled')
        cloud_dir = camera_config.get('@upload_location')
        service_name = camera_config.get('@upload_service')
        clean_cloud_info = None
        if (
            cloud_enabled
            and clean_cloud_enabled
            and camera_id
            and service_name
            and cloud_dir
        ):
            clean_cloud_info = {
                'camera_id': camera_id,
                'service_name': service_name,
                'cloud_dir': cloud_dir,
            }
        if os.path.exists(target_dir):
            # create a sentinel file to make sure the target dir is never removed
            open(os.path.join(target_dir, '.keep'), 'w').close()

        logging.debug(
            f'calling _remove_older_files: {cloud_enabled} {clean_cloud_enabled} {clean_cloud_info}'
        )
        _remove_older_files(target_dir, preserve_moment, clean_cloud_info, exts=exts)


def make_movie_preview(camera_config: dict, full_path: str) -> typing.Union[str, None]:
    framerate = camera_config['framerate']
    pre_capture = camera_config['pre_capture']
    offs = pre_capture / framerate
    offs = max(4, offs * 2)
    path = quote(full_path)
    thumb_path = full_path + '.thumb'

    logging.debug(
        f'creating movie preview for {full_path} with an offset of {offs} seconds...'
    )

    cmd = f'ffmpeg -i {path} -f mjpeg -vframes 1 -ss {offs} -y {path}.thumb'
    logging.debug(f'running command "{cmd}"')

    try:
        utils.call_subprocess(cmd.split(), stderr=subprocess.STDOUT)

    except subprocess.CalledProcessError as e:
        logging.error(f'failed to create movie preview for {full_path}: {e}')

        return None

    try:
        st = os.stat(thumb_path)

    except os.error:
        logging.error(f'failed to create movie preview for {full_path}')

        return None

    if st.st_size == 0:
        logging.debug(
            f'movie probably too short, grabbing first frame from {full_path}...'
        )

        cmd = f'ffmpeg -i {path} -f mjpeg -vframes 1 -ss 0 -y {path}.thumb'
        logging.debug(f'running command "{cmd}"')

        # try again, this time grabbing the very first frame
        try:
            utils.call_subprocess(cmd.split(), stderr=subprocess.STDOUT)

        except subprocess.CalledProcessError as e:
            logging.error(f'failed to create movie preview for {full_path}: {e}')

            return None

        try:
            st = os.stat(thumb_path)

        except os.error:
            logging.error(f'failed to create movie preview for {full_path}')

            return None

    if st.st_size == 0:
        logging.error(f'failed to create movie preview for {full_path}')
        try:
            os.remove(thumb_path)

        except:
            pass

        return None

    return thumb_path


def list_media(camera_config: dict, media_type: str, prefix=None) -> typing.Awaitable:
    fut = Future()
    target_dir = camera_config.get('target_dir')

    if media_type == 'picture':
        exts = _PICTURE_EXTS

    elif media_type == 'movie':
        exts = _MOVIE_EXTS

    # create a subprocess to retrieve media files
    def do_list_media(pipe):
        import mimetypes

        parent_pipe.close()

        mf = _list_media_files(target_dir, exts=exts, prefix=prefix)
        for (p, st) in mf:
            path = p[len(target_dir) :]
            if not path.startswith('/'):
                path = '/' + path

            timestamp = st.st_mtime
            size = st.st_size

            pipe.send(
                {
                    'path': path,
                    'mimeType': mimetypes.guess_type(path)[0]
                    if mimetypes.guess_type(path)[0] is not None
                    else 'video/mpeg',
                    'momentStr': pretty_date_time(
                        datetime.datetime.fromtimestamp(timestamp)
                    ),
                    'momentStrShort': pretty_date_time(
                        datetime.datetime.fromtimestamp(timestamp), short=True
                    ),
                    'sizeStr': utils.pretty_size(size),
                    'timestamp': timestamp,
                }
            )

        pipe.close()

    logging.debug('starting media listing process...')

    (parent_pipe, child_pipe) = multiprocessing.Pipe(duplex=False)
    process = multiprocessing.Process(target=do_list_media, args=(child_pipe,))
    process.start()
    child_pipe.close()

    # poll the subprocess to see when it has finished
    started = datetime.datetime.now()
    media_list = []

    def read_media_list():
        while parent_pipe.poll():
            try:
                media_list.append(parent_pipe.recv())

            except EOFError:
                break

    def poll_process():
        io_loop = IOLoop.instance()
        if process.is_alive():  # not finished yet
            now = datetime.datetime.now()
            delta = now - started
            if delta.seconds < settings.LIST_MEDIA_TIMEOUT:
                io_loop.add_timeout(datetime.timedelta(seconds=0.5), poll_process)
                read_media_list()

            else:  # process did not finish in time
                logging.error('timeout waiting for the media listing process to finish')
                try:
                    os.kill(process.pid, signal.SIGTERM)

                except:
                    pass  # nevermind

                fut.set_result(None)

        else:  # finished
            read_media_list()
            logging.debug(f'media listing process has returned {len(media_list)} files')
            fut.set_result(media_list)

    poll_process()
    return fut


def get_media_path(camera_config, path, media_type):
    target_dir = camera_config.get('target_dir')
    full_path = os.path.join(target_dir, path)
    return full_path


def get_media_content(camera_config, path, media_type):
    target_dir = camera_config.get('target_dir')

    if '..' in path:
        raise Exception('invalid media path')

    full_path = os.path.join(target_dir, path)

    try:
        with open(full_path, 'rb') as f:
            return f.read()

    except Exception as e:
        logging.error(f'failed to read file {full_path}: {str(e)}')

        return None


def get_zipped_content(
    camera_config: dict, media_type: str, group: str
) -> typing.Awaitable:
    fut = Future()
    target_dir = camera_config.get('target_dir')

    if media_type == 'picture':
        exts = _PICTURE_EXTS

    elif media_type == 'movie':
        exts = _MOVIE_EXTS

    working = multiprocessing.Value('b')
    working.value = True

    # create a subprocess to add files to zip
    def do_zip(pipe):
        parent_pipe.close()

        mf = _list_media_files(target_dir, exts=exts, prefix=group)
        paths = []
        for (p, st) in mf:  # @UnusedVariable
            path = p[len(target_dir) :]
            if path.startswith('/'):
                path = path[1:]

            paths.append(path)

        zip_filename = os.path.join(settings.MEDIA_PATH, f'.zip-{int(time.time())}')
        logging.debug(f'adding {len(paths)} files to zip file "{zip_filename}"')

        try:
            with zipfile.ZipFile(zip_filename, mode='w') as f:
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

    logging.debug('starting zip process...')

    (parent_pipe, child_pipe) = multiprocessing.Pipe(duplex=False)
    process = multiprocessing.Process(target=do_zip, args=(child_pipe,))
    process.start()
    child_pipe.close()

    # poll the subprocess to see when it has finished
    started = datetime.datetime.now()

    def poll_process():
        io_loop = IOLoop.instance()
        if working.value:
            now = datetime.datetime.now()
            delta = now - started
            if delta.seconds < settings.ZIP_TIMEOUT:
                io_loop.add_timeout(datetime.timedelta(seconds=0.5), poll_process)

            else:  # process did not finish in time
                logging.error('timeout waiting for the zip process to finish')
                try:
                    os.kill(process.pid, signal.SIGTERM)

                except:
                    pass  # nevermind

                fut.set_result(None)

        else:  # finished
            try:
                data = parent_pipe.recv()
                logging.debug(f'zip process has returned {len(data)} bytes')

            except:
                data = None

            fut.set_result(data)

    poll_process()
    return fut


def make_timelapse_movie(camera_config, framerate, interval, group):
    global _timelapse_process
    global _timelapse_data

    target_dir = camera_config.get('target_dir')
    # save movie_codec as a different variable so it doesn't get lost in the CODEC_MAPPING
    movie_codec = camera_config.get('movie_codec')

    codec = FFMPEG_CODEC_MAPPING.get(movie_codec, movie_codec)
    fmt = FFMPEG_FORMAT_MAPPING.get(movie_codec, movie_codec)
    file_format = FFMPEG_EXT_MAPPING.get(movie_codec, movie_codec)

    # create a subprocess to retrieve media files
    def do_list_media(pipe):
        parent_pipe.close()

        mf = _list_media_files(target_dir, exts=_PICTURE_EXTS, prefix=group)
        for (p, st) in mf:
            timestamp = st.st_mtime

            pipe.send({'path': p, 'timestamp': timestamp})

        pipe.close()

    logging.debug('starting media listing process...')

    (parent_pipe, child_pipe) = multiprocessing.Pipe(duplex=False)
    _timelapse_process = multiprocessing.Process(
        target=do_list_media, args=(child_pipe,)
    )
    _timelapse_process.progress = 0
    _timelapse_process.start()
    _timelapse_data = None

    child_pipe.close()

    started = [datetime.datetime.now()]
    media_list = []

    # use correct extension for the movie_codec
    tmp_filename = os.path.join(
        settings.MEDIA_PATH, f'.{int(time.time())}.{file_format}'
    )

    def read_media_list():
        while parent_pipe.poll():
            try:
                media_list.append(parent_pipe.recv())

            except EOFError:
                break

    def poll_media_list_process():
        io_loop = IOLoop.instance()
        if _timelapse_process.is_alive():  # not finished yet
            now = datetime.datetime.now()
            delta = now - started[0]
            if (
                delta.seconds < settings.TIMELAPSE_TIMEOUT
            ):  # the subprocess has limited time to complete its job
                io_loop.add_timeout(
                    datetime.timedelta(seconds=0.5), poll_media_list_process
                )
                read_media_list()

            else:  # process did not finish in time
                logging.error('timeout waiting for the media listing process to finish')
                try:
                    os.kill(_timelapse_process.pid, signal.SIGTERM)

                except:
                    pass  # nevermind

                _timelapse_process.progress = -1

        else:  # finished
            read_media_list()
            logging.debug(f'media listing process has returned {len(media_list)} files')

            if not media_list:
                _timelapse_process.progress = -1

                return

            pictures = select_pictures(media_list)
            make_movie(pictures)

    def select_pictures(media_list):
        media_list.sort(key=lambda e: e['timestamp'])
        start = media_list[0]['timestamp']
        slices = {}
        max_idx = 0
        for m in media_list:
            offs = m['timestamp'] - start
            pos = float(offs) / interval - 0.5
            idx = int(round(pos))
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

    def make_movie(pictures):
        global _timelapse_process

        # don't specify file format with -f, let ffmpeg work it out from the extension
        cmd = 'rm -f %(tmp_filename)s;'
        cmd += (
            'cat %(jpegs)s | ffmpeg -framerate %(framerate)s -f image2pipe -vcodec mjpeg -i - -vcodec %(codec)s '
            '-format %(format)s -b:v %(bitrate)s -qscale:v 0.1 %(tmp_filename)s'
        )

        bitrate = 9999999

        cmd = cmd % {
            'tmp_filename': tmp_filename,
            'jpegs': ' '.join(('"' + p['path'] + '"') for p in pictures),
            'framerate': framerate,
            'codec': codec,
            'format': fmt,
            'bitrate': bitrate,
        }

        logging.debug(f'executing "{cmd}"')

        _timelapse_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True
        )
        _timelapse_process.progress = 0.01  # 1%

        # make subprocess stdout pipe non-blocking
        fd = _timelapse_process.stdout.fileno()
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        poll_movie_process(pictures)

    def poll_movie_process(pictures):
        global _timelapse_process
        global _timelapse_data

        io_loop = IOLoop.instance()
        if _timelapse_process.poll() is None:  # not finished yet
            io_loop.add_timeout(
                datetime.timedelta(seconds=0.5),
                functools.partial(poll_movie_process, pictures),
            )

            try:
                output = _timelapse_process.stdout.read()
                if not output:
                    return

            except OSError as e:
                if e.errno == errno.EAGAIN:
                    return

                raise

            frame_index = re.findall(br'frame=\s*(\d+)', output)
            try:
                frame_index = int(frame_index[-1])

            except (IndexError, ValueError):
                return

            _timelapse_process.progress = max(0.01, float(frame_index) / len(pictures))

            logging.debug(
                f'timelapse progress: {int(100 * _timelapse_process.progress)} %'
            )

        else:  # finished
            exit_code = _timelapse_process.poll()
            _timelapse_process = None

            if exit_code != 0:
                logging.error('ffmpeg process failed')
                _timelapse_data = None

                try:
                    os.remove(tmp_filename)

                except:
                    pass

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
                    try:
                        os.remove(tmp_filename)

                    except:
                        pass

    poll_media_list_process()


def check_timelapse_movie():
    if _timelapse_process:
        if (
            hasattr(_timelapse_process, 'poll') and _timelapse_process.poll() is None
        ) or (
            hasattr(_timelapse_process, 'is_alive') and _timelapse_process.is_alive()
        ):

            return {'progress': _timelapse_process.progress, 'data': None}

        else:
            return {'progress': _timelapse_process.progress, 'data': _timelapse_data}

    else:
        return {'progress': -1, 'data': _timelapse_data}


def get_media_preview(camera_config, path, media_type, width, height):
    target_dir = camera_config.get('target_dir')
    full_path = os.path.join(target_dir, path)

    if media_type == 'movie':
        if not os.path.exists(full_path + '.thumb'):
            # at this point we expect the thumb to
            # have already been created by the thumbnailer task;
            # if, for some reason that's not the case,
            # we create it right away
            if not make_movie_preview(camera_config, full_path):
                return None

        full_path += '.thumb'

    try:
        with open(full_path, 'rb') as f:
            content = f.read()

    except Exception as e:
        logging.error(f'failed to read file {full_path}: {str(e)}')

        return None

    if width is height is None:
        return content

    bio = io.BytesIO(content)
    try:
        image = Image.open(bio)

    except Exception as e:
        logging.error(f'failed to open media preview image file: {e}')
        return None

    width = width and int(float(width)) or image.size[0]
    height = height and int(float(height)) or image.size[1]

    image.thumbnail((width, height), Image.LINEAR)

    bio = io.BytesIO()
    image.save(bio, format='JPEG')

    return bio.getvalue()


def del_media_content(camera_config, path, media_type):
    target_dir = camera_config.get('target_dir')

    full_path = os.path.join(target_dir, path)

    # create a sentinel file to make sure the target dir is never removed
    open(os.path.join(target_dir, '.keep'), 'w').close()

    try:
        # remove the file itself
        os.remove(full_path)

        # remove the thumb file
        try:
            os.remove(full_path + '.thumb')

        except:
            pass

        # remove the parent directories if empty or contains only thumb files
        dir_path = os.path.dirname(full_path)
        listing = os.listdir(dir_path)
        thumbs = [l for l in listing if l.endswith('.thumb')]

        if len(listing) == len(thumbs):  # only thumbs
            for p in thumbs:
                os.remove(os.path.join(dir_path, p))

        if not listing or len(listing) == len(thumbs):
            logging.debug(f'removing empty directory {dir_path}...')
            os.removedirs(dir_path)

    except Exception as e:
        logging.error(f'failed to remove file {full_path}: {str(e)}')

        raise


def del_media_group(camera_config, group, media_type):
    if media_type == 'picture':
        exts = _PICTURE_EXTS

    else:  # media_type == 'movie'
        exts = _MOVIE_EXTS + ['.thumb']

    target_dir = camera_config.get('target_dir')
    full_path = os.path.join(target_dir, group)

    # create a sentinel file to make sure the target dir is never removed
    open(os.path.join(target_dir, '.keep'), 'w').close()

    mf = _list_media_files(target_dir, exts=exts, prefix=group)
    for (path, st) in mf:  # @UnusedVariable
        try:
            os.remove(path)

        except Exception as e:
            logging.error(f'failed to remove file {full_path}: {str(e)}')

            raise

    # remove the group directory if empty or contains only thumb files
    listing = os.listdir(full_path)
    thumbs = [l for l in listing if l.endswith('.thumb')]

    if len(listing) == len(thumbs):  # only thumbs
        for p in thumbs:
            os.remove(os.path.join(full_path, p))

    if not listing or len(listing) == len(thumbs):
        logging.debug(f'removing empty directory {full_path}...')
        os.removedirs(full_path)


def get_current_picture(camera_config, width, height):
    from motioneye import mjpgclient

    jpg = mjpgclient.get_jpg(camera_config['@id'])

    if jpg is None:
        return None

    if width is height is None:
        return jpg  # no server-side resize needed

    sio = io.StringIO(jpg)
    image = Image.open(sio)

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

    image.thumbnail((width, height), Image.CUBIC)

    sio = io.StringIO()
    image.save(sio, format='JPEG')

    return sio.getvalue()


def get_prepared_cache(key):
    return _prepared_files.pop(key, None)


def set_prepared_cache(data):
    key = hashlib.sha1(str(time.time()).encode()).hexdigest()

    if key in _prepared_files:
        logging.warning(f'key "{key}" already present in prepared cache')

    _prepared_files[key] = data

    def clear():
        if _prepared_files.pop(key, None) is not None:
            logging.warning(
                f'key "{key}" was still present in the prepared cache, removed'
            )

    timeout = 3600  # the user has 1 hour to download the file after creation

    io_loop = IOLoop.instance()
    io_loop.add_timeout(datetime.timedelta(seconds=timeout), clear)

    return key
