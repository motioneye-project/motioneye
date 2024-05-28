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

import errno
import logging
import os.path
import re
import signal
import subprocess
import time
from shlex import quote

from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.ioloop import IOLoop

from motioneye import mediafiles, settings, update, utils
from motioneye.controls.powerctl import PowerControl

_MOTION_CONTROL_TIMEOUT = 5

_started = False
_motion_binary_cache = None
_motion_detected = {}


def find_motion():
    global _motion_binary_cache
    if _motion_binary_cache:
        return _motion_binary_cache

    # binary
    if settings.MOTION_BINARY:
        if os.path.exists(settings.MOTION_BINARY):
            binary = settings.MOTION_BINARY

        else:
            return None, None

    else:  # autodetect motion binary path
        try:
            binary = utils.call_subprocess(['which', 'motion'])

        except subprocess.CalledProcessError:  # not found
            return None, None

    # version
    try:
        output = utils.call_subprocess(quote(binary) + ' -h || true', shell=True)

    except subprocess.CalledProcessError as e:  # not found as
        logging.error(f'motion version could not be found: {e}')
        return None, None

    result = re.findall('motion Version ([^,]+)', output, re.IGNORECASE)
    version = result and result[0] or ''

    logging.debug(f'found motion executable "{binary}" version "{version}"')

    _motion_binary_cache = (binary, version)

    return _motion_binary_cache


def start(deferred=False):
    from motioneye import config, mjpgclient

    if deferred:
        io_loop = IOLoop.current()
        io_loop.add_callback(start, deferred=False)

    global _started

    _started = True

    enabled_local_motion_cameras = config.get_enabled_local_motion_cameras()
    if running() or not enabled_local_motion_cameras:
        return

    logging.debug('searching motion executable')

    binary, version = find_motion()
    if not binary:
        raise Exception('motion executable could not be found')

    logging.debug(f'starting motion executable "{binary}" version "{version}"')

    motion_cfg_path = os.path.join(settings.CONF_PATH, 'motion.conf')
    motion_log_path = os.path.join(settings.LOG_PATH, 'motion.log')
    motion_pid_path = os.path.join(settings.RUN_PATH, 'motion.pid')

    args = [binary, '-n', '-c', motion_cfg_path, '-d']

    if settings.LOG_LEVEL <= logging.DEBUG:
        args.append('9')

    elif settings.LOG_LEVEL <= logging.WARN:
        args.append('5')

    elif settings.LOG_LEVEL <= logging.ERROR:
        args.append('4')

    else:  # fatal, quiet
        args.append('1')

    log_file = open(motion_log_path, 'w')

    process = subprocess.Popen(
        args, stdout=log_file, stderr=log_file, close_fds=True, cwd=settings.CONF_PATH
    )

    # wait 2 seconds to see that the process has successfully started
    for _ in range(20):
        time.sleep(0.1)
        exit_code = process.poll()
        if exit_code is not None and exit_code != 0:
            raise Exception(f'motion failed to start with exit code "{exit_code}"')

    pid = process.pid

    # write the pid to file
    with open(motion_pid_path, 'w') as f:
        f.write(str(pid) + '\n')

    IOLoop.current().spawn_callback(_disable_initial_motion_detection)

    # if mjpg client idle timeout is disabled, create mjpg clients for all cameras by default
    if not settings.MJPG_CLIENT_IDLE_TIMEOUT:
        logging.debug('creating default mjpg clients for local cameras')
        for camera in enabled_local_motion_cameras:
            mjpgclient.get_jpg(camera['@id'])


def stop(invalidate=False):
    from motioneye import mjpgclient

    global _started

    _started = False

    if not running():
        return

    logging.debug('stopping motion')

    mjpgclient.close_all(invalidate=invalidate)

    pid = _get_pid()
    if pid is not None:
        try:
            # send the TERM signal once
            os.kill(pid, signal.SIGTERM)

            # wait 5 seconds for the process to exit
            for i in range(50):  # @UnusedVariable
                os.waitpid(pid, os.WNOHANG)
                time.sleep(0.1)

            # send the KILL signal once
            os.kill(pid, signal.SIGKILL)

            # wait 2 seconds for the process to exit
            for i in range(20):  # @UnusedVariable
                time.sleep(0.1)
                os.waitpid(pid, os.WNOHANG)

            # the process still did not exit
            if settings.ENABLE_REBOOT:
                logging.error('could not terminate the motion process')
                PowerControl.reboot()

            else:
                raise Exception('could not terminate the motion process')

        except OSError as e:
            if e.errno not in (errno.ESRCH, errno.ECHILD):
                raise


def running():
    pid = _get_pid()
    if pid is None:
        return False

    try:
        os.waitpid(pid, os.WNOHANG)
        os.kill(pid, 0)

        # the process is running
        return True

    except OSError as e:
        if e.errno not in (errno.ESRCH, errno.ECHILD):
            raise

    return False


def started():
    return _started


async def get_motion_detection(camera_id) -> utils.GetMotionDetectionResult:
    motion_camera_id = camera_id_to_motion_camera_id(camera_id)
    if motion_camera_id is None:
        error = f'could not find motion camera id for camera with id {camera_id}'
        logging.error(error)
        return utils.GetMotionDetectionResult(None, error=error)

    url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/detection/status'

    request = HTTPRequest(
        url,
        connect_timeout=_MOTION_CONTROL_TIMEOUT,
        request_timeout=_MOTION_CONTROL_TIMEOUT,
    )
    resp = await AsyncHTTPClient().fetch(request)
    if resp.error:
        return utils.GetMotionDetectionResult(None, error=utils.pretty_http_error(resp))

    resp_body = resp.body.decode('utf-8')
    enabled = bool(resp_body.lower().count('active'))

    logging.debug(
        f"motion detection is {['disabled', 'enabled'][enabled]} for camera with id {id}"
    )

    return utils.GetMotionDetectionResult(enabled, None)


async def set_motion_detection(camera_id, enabled):
    motion_camera_id = camera_id_to_motion_camera_id(camera_id)
    if motion_camera_id is None:
        return logging.error(
            f'could not find motion camera id for camera with id {camera_id}'
        )

    if not enabled:
        _motion_detected[camera_id] = False

    logging.debug(
        f"{['disabling', 'enabling'][enabled]} motion detection for camera with id {camera_id}"
    )

    url = f"http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/detection/{['pause', 'start'][enabled]}"

    request = HTTPRequest(
        url,
        connect_timeout=_MOTION_CONTROL_TIMEOUT,
        request_timeout=_MOTION_CONTROL_TIMEOUT,
    )
    resp = await AsyncHTTPClient().fetch(request)
    if resp.error:
        logging.error(
            'failed to {} motion detection for camera with id {}: {}'.format(
                ['disable', 'enable'][enabled],
                camera_id,
                utils.pretty_http_error(resp),
            )
        )

    else:
        logging.debug(
            f"successfully {['disabled', 'enabled'][enabled]} motion detection for camera with id {camera_id}"
        )


async def take_snapshot(camera_id):
    motion_camera_id = camera_id_to_motion_camera_id(camera_id)
    if motion_camera_id is None:
        return logging.error(
            f'could not find motion camera id for camera with id {camera_id}'
        )

    logging.debug(f'taking snapshot for camera with id {camera_id}')

    url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/action/snapshot'

    request = HTTPRequest(
        url,
        connect_timeout=_MOTION_CONTROL_TIMEOUT,
        request_timeout=_MOTION_CONTROL_TIMEOUT,
    )
    resp = await AsyncHTTPClient().fetch(request)
    if resp.error:
        logging.error(
            f'failed to take snapshot for camera with id {camera_id}: {utils.pretty_http_error(resp)}'
        )

    else:
        logging.debug(f'successfully took snapshot for camera with id {camera_id}')


def is_motion_detected(camera_id):
    return _motion_detected.get(camera_id, False)


def set_motion_detected(camera_id, motion_detected):
    if motion_detected:
        logging.debug(f'marking motion detected for camera with id {camera_id}')

    else:
        logging.debug(f'clearing motion detected for camera with id {camera_id}')

    _motion_detected[camera_id] = motion_detected


def camera_id_to_motion_camera_id(camera_id):
    from motioneye import config

    # find the corresponding motion camera_id
    # (which can be different from camera_id)

    main_config = config.get_main()
    cameras = main_config.get('camera', [])

    camera_filename = f'camera-{camera_id}.conf'
    for i, camera in enumerate(cameras):
        if camera != camera_filename:
            continue

        return i + 1

    return None


def motion_camera_id_to_camera_id(motion_camera_id):
    from motioneye import config

    main_config = config.get_main()
    cameras = main_config.get('camera', [])

    try:
        return int(
            re.search(r'camera-(\d+).conf', cameras[int(motion_camera_id) - 1]).group(1)
        )

    except IndexError:
        return None


def is_motion_pre42():
    binary, version = find_motion()
    if not binary:
        return False

    return update.compare_versions(version, '4.2') < 0


def is_motion_post43():
    binary, version = find_motion()
    if not binary:
        return False

    return update.compare_versions(version, '4.4') >= 0  # 4.3.2 > 4.3


def has_h264_omx_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'h264_omx' in codecs.get('h264', {}).get('encoders', set())


def has_h264_v4l2m2m_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'h264_v4l2m2m' in codecs.get('h264', {}).get('encoders', set())


def has_h264_nvenc_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'h264_nvenc' in codecs.get('h264', {}).get('encoders', set())


def has_h264_nvmpi_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'h264_nvmpi' in codecs.get('h264', {}).get('encoders', set())


def has_hevc_nvmpi_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'hevc_nvmpi' in codecs.get('hevc', {}).get('encoders', set())


def has_hevc_nvenc_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'hevc_nvenc' in codecs.get('hevc', {}).get('encoders', set())


def has_h264_qsv_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'h264_qsv' in codecs.get('h264', {}).get('encoders', set())


def has_hevc_qsv_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'hevc_qsv' in codecs.get('hevc', {}).get('encoders', set())


def has_h264_nvenc_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'h264_nvenc' in codecs.get('h264', {}).get('encoders', set())


def has_h264_nvmpi_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'h264_nvmpi' in codecs.get('h264', {}).get('encoders', set())


def has_hevc_nvmpi_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'hevc_nvmpi' in codecs.get('hevc', {}).get('encoders', set())


def has_hevc_nvenc_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'hevc_nvenc' in codecs.get('hevc', {}).get('encoders', set())


def has_h264_qsv_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'h264_qsv' in codecs.get('h264', {}).get('encoders', set())


def has_hevc_qsv_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'hevc_qsv' in codecs.get('hevc', {}).get('encoders', set())


def resolution_is_valid(width, height):
    # width & height must be be modulo 8

    if width % 8:
        return False

    if height % 8:
        return False

    return True


async def _disable_initial_motion_detection():
    from motioneye import config

    for camera_id in config.get_camera_ids():
        camera_config = config.get_camera(camera_id)
        if not utils.is_local_motion_camera(camera_config):
            continue

        if not camera_config['@motion_detection']:
            logging.debug(
                f'motion detection disabled by config for camera with id {camera_id}'
            )
            await set_motion_detection(camera_id, False)


def _get_pid():
    motion_pid_path = os.path.join(settings.RUN_PATH, 'motion.pid')

    # read the pid from file
    try:
        with open(motion_pid_path) as f:
            return int(f.readline().strip())

    except (OSError, ValueError):
        return None
