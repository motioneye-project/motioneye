
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
import multiprocessing
import os.path
import signal
import sys 

from tornado.httpclient import AsyncHTTPClient
from tornado.web import Application

import handlers
import logging
import settings
import template


def load_settings():
    # TODO use optparse
#     length = len(sys.argv) - 1
#     for i in xrange(length):
#         arg = sys.argv[i + 1]
#         
#         if not arg.startswith('--'):
#             continue
#         
#         next_arg = None
#         if i < length - 1:
#             next_arg = sys.argv[i + 2]
#         
#         name = arg[2:].upper().replace('-', '_')
#         
#         if hasattr(settings, name):
#             curr_value = getattr(settings, name)
#             
#             if next_arg.lower() == 'debug':
#                 next_arg = logging.DEBUG
#             
#             elif next_arg.lower() == 'info':
#                 next_arg = logging.INFO
#             
#             elif next_arg.lower() == 'warn':
#                 next_arg = logging.WARN
#             
#             elif next_arg.lower() == 'error':
#                 next_arg = logging.ERROR
#             
#             elif next_arg.lower() == 'fatal':
#                 next_arg = logging.FATAL
#             
#             elif next_arg.lower() == 'true':
#                 next_arg = True
#             
#             elif next_arg.lower() == 'false':
#                 next_arg = False
#             
#             elif isinstance(curr_value, int):
#                 next_arg = int(next_arg)
#             
#             elif isinstance(curr_value, float):
#                 next_arg = float(next_arg)
# 
#             setattr(settings, name, next_arg)
#         
#         else:
#             return arg[2:]

    if not os.path.exists(settings.CONF_PATH):
        logging.fatal('config directory "%s" does not exist' % settings.CONF_PATH)
        sys.exit(-1)
    
    if not os.path.exists(settings.RUN_PATH):
        logging.fatal('pid directory "%s" does not exist' % settings.RUN_PATH)
        sys.exit(-1)

    if not os.path.exists(settings.LOG_PATH):
        logging.fatal('log directory "%s" does not exist' % settings.LOG_PATH)
        sys.exit(-1)

    if not os.path.exists(settings.MEDIA_PATH):
        logging.fatal('media directory "%s" does not exist' % settings.MEDIA_PATH)
        sys.exit(-1)


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


def configure_logging(module=None):
    if module:
        format = '%(asctime)s: [{module}] %(levelname)s: %(message)s'.format(module=module)
        
    else:
        format = '%(asctime)s: %(levelname)s: %(message)s'

    logging.basicConfig(filename=None, level=settings.LOG_LEVEL,
            format=format, datefmt='%Y-%m-%d %H:%M:%S')

    logging.getLogger('tornado').setLevel(logging.WARN)


def configure_tornado():
    AsyncHTTPClient.configure('tornado.curl_httpclient.CurlAsyncHTTPClient', max_clients=16)


def test_requirements():
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
    
    import mediafiles
    has_ffmpeg = mediafiles.find_ffmpeg() is not None
    
    import motionctl
    has_motion = motionctl.find_motion() is not None
    
    import v4l2ctl
    has_v4lutils = v4l2ctl.find_v4l2_ctl() is not None

    import smbctl
    if settings.SMB_SHARES and smbctl.find_mount_cifs() is None:
        logging.fatal('please install cifs-utils')
        sys.exit(-1)

    if not has_ffmpeg:
        logging.info('ffmpeg not installed')

    if not has_motion:
        logging.info('motion not installed')

    if not has_v4lutils:
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


def run_server():
    import cleanup
    import motionctl
    import thumbnailer
    import tornado.ioloop
    import smbctl

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


def log_request(handler):
    if handler.get_status() < 400:
        log_method = logging.debug
    
    elif handler.get_status() < 500:
        log_method = logging.warning
    
    else:
        log_method = logging.error
    
    request_time = 1000.0 * handler.request.request_time()
    log_method("%d %s %.2fms", handler.get_status(),
               handler._request_summary(), request_time)


application = Application(
    [
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
    ],
    debug=False,
    log_function=log_request,
    static_path=settings.STATIC_PATH,
    static_url_prefix=settings.STATIC_URL
)

template.add_context('STATIC_URL', settings.STATIC_URL)


def main():
    import motioneye
    
    load_settings()
    configure_signals()
    configure_logging()
    test_requirements()
    configure_tornado()

    logging.info('hello! this is motionEye %s' % motioneye.VERSION)
    
    if settings.SMB_SHARES:
        import smbctl

        stop, start = smbctl.update_mounts()  # @UnusedVariable
        if start:
            start_motion()

    else:
        start_motion()

    start_cleanup()
    start_wsswitch()

    if settings.THUMBNAILER_INTERVAL:
        start_thumbnailer()

    run_server()

    logging.info('bye!')
