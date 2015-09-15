
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

import atexit
import datetime
import logging
import multiprocessing
import os
import signal
import sys
import time

from tornado.web import Application

import handlers
import settings
import template


_PID_FILE = 'motioneye.pid'


class Daemon(object):
    def __init__(self, pid_file, run_callback=None):
        self.pid_file = pid_file
        self.run_callback = run_callback

    def daemonize(self):
        # first fork
        try: 
            if os.fork() > 0: # parent
                sys.exit(0)

        except OSError, e: 
            sys.stderr.write('fork() failed: %s\n' % e.strerror)
            sys.exit(-1)

        # separate from parent
        os.setsid()
        os.umask(0) 

        # second fork
        try: 
            if os.fork() > 0: # parent 
                sys.exit(0) 
        
        except OSError, e: 
            sys.stderr.write('fork() failed: %s\n' % e.strerror)
            sys.exit(-1) 

        # redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        si = file('/dev/null', 'r')
        so = file('/dev/null', 'a+')
        se = file('/dev/null', 'a+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        # pid file
        atexit.register(self.del_pid)
        with open(self.pid_file, 'w') as f:
            f.write('%s\n' % os.getpid())

    def del_pid(self):
        try:
            os.remove(self.pid_file)
        
        except:
            pass
    
    def running(self):
        try:
            with open(self.pid_file) as f:
                pid = int(f.read().strip())

        except:
            return None

        try:
            os.kill(pid, 0)
            return pid
        
        except:
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
            sys.stderr.write('failed to terminate server: %s\n' % e)

        for i in xrange(50):  # @UnusedVariable
            try:
                os.kill(pid, 0)
                time.sleep(0.1)

            except OSError as e:
                if str(e).count('No such process'):
                    self.del_pid()
                    sys.stdout.write('server stopped\n')
                    break

                else:
                    sys.stderr.write('failed to terminate server: %s\n' % e)
                    sys.exit(-11)
        
        else:
            sys.stderr.write('server failed to stop, killing it\n')
            try:
                os.kill(pid, signal.SIGKILL)

            except:
                pass


def _log_request(handler):
    if handler.get_status() < 400:
        log_method = logging.debug
    
    elif handler.get_status() < 500:
        log_method = logging.warning
    
    else:
        log_method = logging.error
    
    request_time = 1000.0 * handler.request.request_time()
    log_method("%d %s %.2fms", handler.get_status(),
               handler._request_summary(), request_time)

handler_mapping = [
    (r'^/$', handlers.MainHandler),
    (r'^/config/main/(?P<op>set|get)/?$', handlers.ConfigHandler),
    (r'^/config/(?P<camera_id>\d+)/(?P<op>get|set|rem|set_preview)/?$', handlers.ConfigHandler),
    (r'^/config/(?P<op>add|list|backup|restore)/?$', handlers.ConfigHandler),
    (r'^/picture/(?P<camera_id>\d+)/(?P<op>current|list|frame)/?$', handlers.PictureHandler),
    (r'^/picture/(?P<camera_id>\d+)/(?P<op>download|preview|delete)/(?P<filename>.+?)/?$', handlers.PictureHandler),
    (r'^/picture/(?P<camera_id>\d+)/(?P<op>zipped|timelapse|delete_all)/(?P<group>.+?)/?$', handlers.PictureHandler),
    (r'^/movie/(?P<camera_id>\d+)/(?P<op>list)/?$', handlers.MovieHandler),
    (r'^/movie/(?P<camera_id>\d+)/(?P<op>download|preview|delete)/(?P<filename>.+?)/?$', handlers.MovieHandler),
    (r'^/movie/(?P<camera_id>\d+)/(?P<op>delete_all)/(?P<group>.+?)/?$', handlers.MovieHandler),
    (r'^/_relay_event/?$', handlers.RelayEventHandler),
    (r'^/log/(?P<name>\w+)/?$', handlers.LogHandler),
    (r'^/update/?$', handlers.UpdateHandler),
    (r'^/power/(?P<op>shutdown|reboot)/?$', handlers.PowerHandler),
    (r'^/version/?$', handlers.VersionHandler),
    (r'^/login/?$', handlers.LoginHandler),
    (r'^.*$', handlers.NotFoundHandler),
]


def configure_signals():
    def bye_handler(signal, frame):
        import tornado.ioloop
        
        logging.info('interrupt signal received, shutting down...')

        # shut down the IO loop if it has been started
        ioloop = tornado.ioloop.IOLoop.instance()
        ioloop.stop()
        
    def child_handler(signal, frame):
        # this is required for the multiprocessing mechanism to work
        multiprocessing.active_children()

    signal.signal(signal.SIGINT, bye_handler)
    signal.signal(signal.SIGTERM, bye_handler)
    signal.signal(signal.SIGCHLD, child_handler)


def test_requirements():
    if not os.access(settings.CONF_PATH, os.W_OK):
        logging.fatal('config directory "%s" does not exist or is not writable' % settings.CONF_PATH)
        sys.exit(-1)
    
    if not os.access(settings.RUN_PATH, os.W_OK):
        logging.fatal('pid directory "%s" does not exist or is not writable' % settings.RUN_PATH)
        sys.exit(-1)

    if not os.access(settings.LOG_PATH, os.W_OK):
        logging.fatal('log directory "%s" does not exist or is not writable' % settings.LOG_PATH)
        sys.exit(-1)

    if not os.access(settings.MEDIA_PATH, os.W_OK):
        logging.fatal('media directory "%s" does not exist or is not writable' % settings.MEDIA_PATH)
        sys.exit(-1)

    if os.geteuid() != 0:
        if settings.SMB_SHARES:
            print('SMB_SHARES require root privileges')
            return False

        if settings.ENABLE_REBOOT:
            print('reboot requires root privileges')
            return False

    try:
        import tornado  # @UnusedImport

    except ImportError:
        logging.fatal('please install tornado version 3.1 or greater')
        sys.exit(-1)

    try:
        import jinja2  # @UnusedImport

    except ImportError:
        logging.fatal('please install jinja2')
        sys.exit(-1)

    try:
        import PIL.Image  # @UnusedImport

    except ImportError:
        logging.fatal('please install pillow or PIL')
        sys.exit(-1)

    try:
        import pycurl  # @UnusedImport

    except ImportError:
        logging.fatal('please install pycurl')
        sys.exit(-1)
    
    import motionctl
    has_motion = motionctl.find_motion() is not None
    
    import mediafiles
    has_ffmpeg = mediafiles.find_ffmpeg() is not None
    
    import v4l2ctl
    has_v4lutils = v4l2ctl.find_v4l2_ctl() is not None

    import smbctl
    if settings.SMB_SHARES and smbctl.find_mount_cifs() is None:
        logging.fatal('please install cifs-utils')
        sys.exit(-1)

    if not has_motion:
        logging.info('motion not installed')

    if not has_ffmpeg:
        if has_motion:
            logging.warn('you have motion installed, but no ffmpeg')
        
        else:
            logging.info('ffmpeg not installed')

    if not has_v4lutils:
        if has_motion:
            logging.warn('you have motion installed, but no v4l-utils')

        else:
            logging.info('v4l-utils not installed')

        
def start_motion():
    import tornado.ioloop
    import config
    import motionctl

    ioloop = tornado.ioloop.IOLoop.instance()
    
    # add a motion running checker
    def checker():
        if ioloop._stopped:
            return
            
        if not motionctl.running() and motionctl.started() and config.get_enabled_local_motion_cameras():
            try:
                logging.error('motion not running, starting it')
                motionctl.start()
            
            except Exception as e:
                logging.error('failed to start motion: %(msg)s' % {
                        'msg': unicode(e)}, exc_info=True)

        ioloop.add_timeout(datetime.timedelta(seconds=settings.MOTION_CHECK_INTERVAL), checker)
    
    motionctl.start()
        
    ioloop.add_timeout(datetime.timedelta(seconds=settings.MOTION_CHECK_INTERVAL), checker)


def start_cleanup():
    import cleanup

    cleanup.start()
    logging.info('cleanup started')


def start_wsswitch():
    import wsswitch

    wsswitch.start()
    logging.info('wsswitch started')


def start_thumbnailer():
    import thumbnailer

    thumbnailer.start()
    logging.info('thumbnailer started')


def parse_options(parser, args):
    parser.add_argument('-b', help='start the server in background (daemonize)',
            action='store_true', dest='background', default=False)

    return parser.parse_args(args)


def run():
    import cleanup
    import motionctl
    import motioneye
    import smbctl
    import thumbnailer
    import tornado.ioloop

    configure_signals()
    logging.info('hello! this is motionEye server %s' % motioneye.VERSION)

    test_requirements()

    if settings.SMB_SHARES:

        stop, start = smbctl.update_mounts()  # @UnusedVariable
        if start:
            start_motion()

    else:
        start_motion()

    start_cleanup()
    start_wsswitch()

    if settings.THUMBNAILER_INTERVAL:
        start_thumbnailer()

    template.add_context('static_path', settings.BASE_PATH + '/static/')
    
    application = Application(handler_mapping, debug=False, log_function=_log_request,
            static_path=settings.STATIC_PATH, static_url_prefix='/static/')
    
    application.listen(settings.PORT, settings.LISTEN)
    logging.info('server started')
    
    tornado.ioloop.IOLoop.instance().start()

    logging.info('server stopped')
    
    if thumbnailer.running():
        thumbnailer.stop()
        logging.info('thumbnailer stopped')

    if cleanup.running():
        cleanup.stop()
        logging.info('cleanup stopped')

    if motionctl.running():
        motionctl.stop()
        logging.info('motion stopped')
    
    if settings.SMB_SHARES:
        smbctl.umount_all()
        logging.info('SMB shares unmounted')

    logging.info('bye!')


def main(parser, args, command):
    import meyectl
    
    options = parse_options(parser, args)
    
    meyectl.configure_logging('motioneye', options.background or options.log_to_file)
    meyectl.configure_tornado()

    if command == 'start':
        if options.background:
            daemon = Daemon(
                    pid_file=os.path.join(settings.RUN_PATH, _PID_FILE),
                    run_callback=run)
            daemon.start()
            
        else:
            run()

    elif command == 'stop':
        daemon = Daemon(pid_file=os.path.join(settings.RUN_PATH, _PID_FILE))
        daemon.stop()
