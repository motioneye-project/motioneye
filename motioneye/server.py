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

import atexit
import logging
import multiprocessing
import os
import re
import signal
import sys
import time
from collections.abc import Sequence
from secrets import token_bytes

from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.web import Application

from motioneye import config, migration, settings, template
from motioneye.controls import smbctl, v4l2ctl
from motioneye.handlers.action import ActionHandler
from motioneye.handlers.base import ManifestHandler, NotFoundHandler
from motioneye.handlers.config import ConfigHandler
from motioneye.handlers.log import LogHandler
from motioneye.handlers.login import LoginHandler
from motioneye.handlers.logout import LogoutHandler
from motioneye.handlers.main import MainHandler
from motioneye.handlers.movie import MovieHandler
from motioneye.handlers.movie_playback import MovieDownloadHandler, MoviePlaybackHandler
from motioneye.handlers.picture import PictureHandler
from motioneye.handlers.power import PowerHandler
from motioneye.handlers.prefs import PrefsHandler
from motioneye.handlers.relay_event import RelayEventHandler
from motioneye.utils import authstate

_PID_FILE = 'motioneye.pid'
_CURRENT_PICTURE_REGEX = re.compile(r'^/picture/\d+/current')


class Daemon:
    def __init__(self, pid_file, run_callback=None):
        self.pid_file = pid_file
        self.run_callback = run_callback

    def daemonize(self):
        # first fork
        try:
            if os.fork() > 0:  # parent
                sys.exit(0)

        except OSError as e:
            sys.stderr.write(f'fork() failed: {e.strerror}\n')
            sys.exit(-1)

        # separate from parent
        os.setsid()
        os.umask(0)

        # second fork
        try:
            if os.fork() > 0:  # parent
                sys.exit(0)

        except OSError as e:
            sys.stderr.write(f'fork() failed: {e.strerror}\n')
            sys.exit(-1)

        # redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        with open(os.devnull) as si:
            os.dup2(si.fileno(), sys.stdin.fileno())
        with open(os.devnull, 'a+') as so:
            os.dup2(so.fileno(), sys.stdout.fileno())
        with open(os.devnull, 'a+') as se:
            os.dup2(se.fileno(), sys.stderr.fileno())

        # pid file
        atexit.register(self.del_pid)
        with open(self.pid_file, 'w') as f:
            f.write(f'{os.getpid()}\n')

    def del_pid(self):
        try:
            os.remove(self.pid_file)

        except Exception:
            sys.stderr.write('failed to remove pid file.\n')

    def running(self):
        try:
            with open(self.pid_file) as f:
                pid = int(f.read().strip())

        except Exception:
            return None

        try:
            os.kill(pid, 0)
            return pid

        except Exception:
            return None

    def start(self):
        if self.running():
            sys.stderr.write('server is already running\n')
            sys.exit(-1)

        self.daemonize()
        sys.stdout.write('server started\n')
        self.run_callback()

    def stop(self):
        pid = self.running()
        if not pid:
            sys.stderr.write('server is not running\n')
            sys.exit(-1)

        try:
            os.kill(pid, signal.SIGTERM)

        except Exception as e:
            sys.stderr.write(f'failed to terminate server: {e}\n')

        for _i in range(50):
            try:
                os.kill(pid, 0)
                time.sleep(0.1)

            except OSError as e:
                if str(e).count('No such process'):
                    self.del_pid()
                    sys.stdout.write('server stopped\n')
                    break

                else:
                    sys.stderr.write(f'failed to terminate server: {e}\n')
                    sys.exit(-11)

        else:
            sys.stderr.write('server failed to stop, killing it\n')
            try:
                os.kill(pid, signal.SIGKILL)

            except Exception:
                sys.stderr.write('failed to kill...\n')


def _log_request(handler):
    log_method = None

    if handler.get_status() < 400:
        if not _CURRENT_PICTURE_REGEX.match(handler.request.uri):
            log_method = logging.debug

    elif handler.get_status() < 500:
        log_method = logging.warning

    else:
        log_method = logging.error

    if log_method:
        request_time = 1000.0 * handler.request.request_time()
        log_method(
            "%d %s %.2fms",
            handler.get_status(),
            handler._request_summary(),
            request_time,
        )


handler_mapping: Sequence[tuple] = [
    (r'^/$', MainHandler),
    (r'^/manifest.json$', ManifestHandler),
    (r'^/config/main/(?P<op>set|get)/?$', ConfigHandler),
    (
        r'^/config/(?P<camera_id>\d+)/(?P<op>get|set|rem|test|authorize|credentials)/?$',
        ConfigHandler,
    ),
    (r'^/config/(?P<op>add|list|backup|restore)/?$', ConfigHandler),
    (r'^/picture/(?P<camera_id>\d+)/(?P<op>current|list|frame)/?$', PictureHandler),
    (
        r'^/picture/(?P<camera_id>\d+)/(?P<op>download|preview|delete)/(?P<filename>.+?)/?$',
        PictureHandler,
    ),
    (
        r'^/picture/(?P<camera_id>\d+)/(?P<op>zipped|timelapse|delete_all)/(?P<group>.*?)/?$',
        PictureHandler,
    ),
    (r'^/movie/(?P<camera_id>\d+)/(?P<op>list)/?$', MovieHandler),
    (
        r'^/movie/(?P<camera_id>\d+)/(?P<op>preview|delete)/(?P<filename>.+?)/?$',
        MovieHandler,
    ),
    (r'^/movie/(?P<camera_id>\d+)/(?P<op>delete_all)/(?P<group>.*?)/?$', MovieHandler),
    (
        r'^/movie/(?P<camera_id>\d+)/playback/(?P<filename>.+?)/?$',
        MoviePlaybackHandler,
        {'path': r''},
    ),
    (
        r'^/movie/(?P<camera_id>\d+)/download/(?P<filename>.+?)/?$',
        MovieDownloadHandler,
        {'path': r''},
    ),
    (r'^/action/(?P<camera_id>\d+)/(?P<action>\w+)/?$', ActionHandler),
    (r'^/prefs/(?P<key>\w+)?/?$', PrefsHandler),
    (r'^/_relay_event/?$', RelayEventHandler),
    (r'^/log/(?P<name>\w+)/?$', LogHandler),
    (r'^/power/(?P<op>shutdown|reboot)/?$', PowerHandler),
    (r'^/login/?$', LoginHandler),
    (r'^/logout/?$', LogoutHandler),
    (r'^.*$', NotFoundHandler),
]


_motion_checker: PeriodicCallback | None = None


def configure_signals():
    def bye_handler():
        logging.info(_('interrompa signalo ricevita, fermanta …'))

        stop_motion_checker()

        # shut down the IO loop if it has been started
        IOLoop.current().stop()

    def child_handler(signal, frame):
        # this is required for the multiprocessing mechanism to work
        multiprocessing.active_children()

    asyncio_loop = IOLoop.current().asyncio_loop
    asyncio_loop.add_signal_handler(signal.SIGINT, bye_handler)
    asyncio_loop.add_signal_handler(signal.SIGTERM, bye_handler)
    signal.signal(signal.SIGCHLD, child_handler)

    if sys.version_info < (3, 12):
        # processes forked by multiprocessing inherit the signal wakeup fd of the
        # handlers above, so a signal sent to one of them would stop this server
        os.register_at_fork(after_in_child=lambda: signal.set_wakeup_fd(-1))


def test_requirements():
    if not os.access(settings.CONF_PATH, os.W_OK):
        logging.fatal(
            f'config directory "{settings.CONF_PATH}" does not exist or is not writable'
        )
        sys.exit(-1)

    if not os.access(settings.RUN_PATH, os.W_OK):
        logging.fatal(
            f'pid directory "{settings.RUN_PATH}" does not exist or is not writable'
        )
        sys.exit(-1)

    if settings.LOG_TO_FILE and not os.access(settings.LOG_PATH, os.W_OK):
        logging.fatal(
            f'log directory "{settings.LOG_PATH}" does not exist or is not writable'
        )
        sys.exit(-1)

    if not os.access(settings.MEDIA_PATH, os.W_OK):
        logging.fatal(
            f'media directory "{settings.MEDIA_PATH}" does not exist or is not writable'
        )
        sys.exit(-1)

    if os.geteuid() != 0 and settings.SMB_SHARES:
        logging.fatal(_('smb-akcioj postulas radikajn privilegiojn'))
        sys.exit(-1)

    try:
        import tornado  # noqa: F401

    except ImportError:
        logging.fatal(_('bonvolu instali tornado version 3.1 aŭ pli'))
        sys.exit(-1)

    try:
        import jinja2  # noqa: F401

    except ImportError:
        logging.fatal(_('bonvolu instali jinja2'))
        sys.exit(-1)

    try:
        import PIL.Image  # noqa: F401

    except ImportError:
        logging.fatal(_('bonvolu instali pillow aŭ PIL'))
        sys.exit(-1)

    try:
        import pycurl  # noqa: F401

    except ImportError:
        logging.fatal(_('bonvolu instali pycurl'))
        sys.exit(-1)

    from motioneye import motionctl

    has_motion = motionctl.find_motion()[0] is not None

    from motioneye import mediafiles

    has_ffmpeg = mediafiles.find_ffmpeg() is not None

    has_v4lutils = v4l2ctl.find_v4l2_ctl() is not None

    if settings.SMB_SHARES and smbctl.find_mount_cifs() is None:
        logging.fatal('please install cifs-utils')
        sys.exit(-1)

    if not has_motion:
        logging.info('motion not installed')

    if not has_ffmpeg:
        if has_motion:
            logging.warning('you have motion installed, but no ffmpeg')

        else:
            logging.info('ffmpeg not installed')

    if not has_v4lutils:
        if has_motion:
            logging.warning('you have motion installed, but no v4l-utils')

        else:
            logging.info('v4l-utils not installed')


def make_media_folders():
    from motioneye import config

    config.get_main()  # just to have main config already loaded

    camera_ids = config.get_camera_ids()
    for camera_id in camera_ids:
        camera_config = config.get_camera(camera_id)
        if 'target_dir' in camera_config and not os.path.exists(
            camera_config['target_dir']
        ):
            try:
                os.makedirs(camera_config['target_dir'])

            except Exception as e:
                logging.error(
                    'failed to create root media folder "{}" for camera with id {}: {}'.format(
                        camera_config['target_dir'], camera_id, e
                    )
                )


def start_motion():
    global _motion_checker

    from motioneye import config, motionctl

    def checker():
        if (
            not motionctl.running()
            and motionctl.started()
            and config.get_enabled_local_motion_cameras()
        ):
            try:
                logging.error('motion not running, starting it')
                motionctl.start()

            except Exception:
                logging.error('failed to start motion')

    try:
        motionctl.start()

    except Exception:
        logging.exception('failed to start motion')

    stop_motion_checker()
    _motion_checker = PeriodicCallback(checker, settings.MOTION_CHECK_INTERVAL * 1000)
    _motion_checker.start()


def stop_motion_checker():
    global _motion_checker

    if _motion_checker is not None:
        _motion_checker.stop()
        _motion_checker = None


def parse_options(parser, args):
    parser.add_argument(
        '-b',
        help='start the server in background (daemonize)',
        action='store_true',
        dest='background',
        default=False,
    )

    return parser.parse_args(args)


def make_app(debug: bool = False) -> Application:
    return Application(
        handler_mapping,
        debug=debug,
        log_function=_log_request,
        static_path=settings.STATIC_PATH,
        static_url_prefix='/static/',
        cookie_secret=token_bytes(32),
    )


def listen(application: Application) -> None:
    application.listen(settings.PORT, settings.LISTEN)

    # motion relays its events to 127.0.0.1 (see relayevent.sh), and the relay
    # event API only accepts local requests, so listen there as well when the
    # configured address does not include it
    if settings.LISTEN not in ('', '0.0.0.0', '127.0.0.1', 'localhost'):  # nosec: B104
        try:
            application.listen(settings.PORT, '127.0.0.1')

        except OSError as e:
            logging.warning(
                f'could not also listen on 127.0.0.1:{settings.PORT} for motion event relays: {e}'
            )


def run():
    from motioneye import VERSION, cleanup, mjpgclient, motionctl, tasks, wsswitch
    from motioneye.controls import smbctl

    configure_signals()
    logging.info(_('saluton! ĉi tio estas motionEye-servilo ') + VERSION)

    test_requirements()
    make_media_folders()

    legacy_pickle_file = os.path.join(settings.CONF_PATH, 'tasks.pickle')
    if os.path.exists(legacy_pickle_file):
        logging.warning(f'removing legacy tasks pickle file {legacy_pickle_file!r}')
        os.remove(legacy_pickle_file)

    state = authstate.build_password_hash_state(config.get_main())
    authstate.set_password_hash_state(state)
    if not authstate.validate_password_hash_state(state):
        logging.warning(
            _(
                'The admin and/or surveillance user has no password assigned. '
                'Please login to the web interface to set both passwords.'
            )
        )

    migration.migrate_cameras()  # before motion reads the camera configs

    if settings.SMB_SHARES:
        _stop, start = smbctl.update_mounts()
        if start:
            start_motion()

    else:
        start_motion()

    wsswitch.start()
    tasks.start()
    cleanup.start()

    if settings.MJPG_CLIENT_TIMEOUT:
        mjpgclient.start()
        logging.info(_('mjpg klienta rubo-kolektanto komenciĝis'))

    if settings.SMB_SHARES:
        smbctl.start()
        logging.info('smb mounts started')

    template.add_context('static_path', 'static/')
    template.add_context('lingvo', settings.lingvo)

    # Create the Tornado application with secure cookie settings
    application = make_app(debug=False)
    listen(application)
    logging.info(_('servilo komenciĝis'))

    io_loop = IOLoop.current()
    # we need to reset the loop's PID to fix PID checks when running in daemon mode
    io_loop._pid = os.getpid()
    io_loop.start()

    # shutdown sequence begins once io_loop.start() returns
    logging.info(_('servilo haltis'))

    stop_motion_checker()
    cleanup.stop()
    tasks.stop()

    if motionctl.running():
        motionctl.stop()
        logging.info(_('motion haltis'))

    if settings.SMB_SHARES:
        smbctl.stop()
        logging.info('smb mounts stopped')

    logging.info(_('adiaŭ!'))


def main(parser, args, command):
    from motioneye import meyectl

    options = parse_options(parser, args)

    # daemon mode redirects stdout/stderr to /dev/null,
    # so logging to file is the only way to preserve any output
    if options.background:
        settings.LOG_TO_FILE = True

    meyectl.configure_logging('motioneye')
    meyectl.configure_tornado()

    if command == 'start':
        if options.background:
            daemon = Daemon(
                pid_file=os.path.join(settings.RUN_PATH, _PID_FILE), run_callback=run
            )
            daemon.start()

        else:
            run()

    elif command == 'stop':
        daemon = Daemon(pid_file=os.path.join(settings.RUN_PATH, _PID_FILE))
        daemon.stop()
