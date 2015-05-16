#!/usr/bin/env python

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
import imp
import inspect
import logging
import multiprocessing
import os.path
import re
import signal
import sys

from tornado.httpclient import AsyncHTTPClient

# test if a --settings directive has been supplied
for i in xrange(1, len(sys.argv) - 1):
    if sys.argv[i] == '--settings':
        settings_module = sys.argv[i + 1]
        imp.load_source('settings', settings_module)

sys.path.append(os.path.join(os.path.dirname(sys.argv[0]), 'src'))

import settings
import update

VERSION = '0.24'


def _configure_settings():
    def set_default_setting(name, value):
        if not hasattr(settings, name):
            setattr(settings, name, value)
    
    set_default_setting('PROJECT_PATH', os.path.dirname(sys.argv[0]))
    set_default_setting('TEMPLATE_PATH', os.path.join(settings.PROJECT_PATH, 'templates'))
    set_default_setting('STATIC_PATH', os.path.join(settings.PROJECT_PATH, 'static'))
    set_default_setting('STATIC_URL', '/static/')
    set_default_setting('CONF_PATH', os.path.join(settings.PROJECT_PATH, 'conf'))
    set_default_setting('RUN_PATH', os.path.join(settings.PROJECT_PATH, 'run'))
    set_default_setting('LOG_PATH', os.path.join(settings.PROJECT_PATH, 'log'))
    set_default_setting('MEDIA_PATH', os.path.join(settings.PROJECT_PATH, 'media'))
    set_default_setting('MOTION_BINARY', None)
    set_default_setting('LOG_LEVEL', logging.INFO)
    set_default_setting('LISTEN', '0.0.0.0')
    set_default_setting('PORT', 8765)
    set_default_setting('MOUNT_CHECK_INTERVAL', 300)
    set_default_setting('MOTION_CHECK_INTERVAL', 10)
    set_default_setting('CLEANUP_INTERVAL', 43200)
    set_default_setting('THUMBNAILER_INTERVAL', 60)
    set_default_setting('REMOTE_REQUEST_TIMEOUT', 10)
    set_default_setting('MJPG_CLIENT_TIMEOUT', 10)
    set_default_setting('PICTURE_CACHE_SIZE', 8)
    set_default_setting('PICTURE_CACHE_LIFETIME', 60)
    set_default_setting('SMB_SHARES', False)
    set_default_setting('SMB_MOUNT_ROOT', '/media')
    set_default_setting('WPA_SUPPLICANT_CONF', None)
    set_default_setting('LOCAL_TIME_FILE', None)
    set_default_setting('ENABLE_REBOOT', False)
    set_default_setting('SMTP_TIMEOUT', 60)
    set_default_setting('ZIP_TIMEOUT', 500)

    length = len(sys.argv) - 1
    for i in xrange(length):
        arg = sys.argv[i + 1]
        
        if not arg.startswith('--'):
            continue
        
        next_arg = None
        if i < length - 1:
            next_arg = sys.argv[i + 2]
        
        name = arg[2:].upper().replace('-', '_')
        
        if name == 'HELP':
            _print_help()
            sys.exit(0)
        
        if hasattr(settings, name):
            curr_value = getattr(settings, name)
            
            if next_arg.lower() == 'debug':
                next_arg = logging.DEBUG
            
            elif next_arg.lower() == 'info':
                next_arg = logging.INFO
            
            elif next_arg.lower() == 'warn':
                next_arg = logging.WARN
            
            elif next_arg.lower() == 'error':
                next_arg = logging.ERROR
            
            elif next_arg.lower() == 'fatal':
                next_arg = logging.FATAL
            
            elif next_arg.lower() == 'true':
                next_arg = True
            
            elif next_arg.lower() == 'false':
                next_arg = False
            
            elif isinstance(curr_value, int):
                next_arg = int(next_arg)
            
            elif isinstance(curr_value, float):
                next_arg = float(next_arg)

            setattr(settings, name, next_arg)
        
        else:
            return arg[2:]
    
    try:
        os.makedirs(settings.CONF_PATH)
        
    except:
        pass
    
    try:
        os.makedirs(settings.RUN_PATH)

    except:
        pass

    try:
        os.makedirs(settings.LOG_PATH)

    except:
        pass

    try:
        os.makedirs(settings.MEDIA_PATH)

    except:
        pass


def _test_requirements():
    if os.geteuid() != 0:
        if settings.SMB_SHARES:
            print('SMB_SHARES require root privileges')
            return False

        if settings.ENABLE_REBOOT:
            print('reboot requires root privileges')
            return False

    try:
        import tornado  # @UnusedImport
        has_tornado = True

    except ImportError:
        has_tornado = False

    if update.compare_versions(tornado.version, '3.1') < 0:
        has_tornado = False

    try:
        import jinja2  # @UnusedImport
        has_jinja2 = True
    
    except ImportError:
        has_jinja2 = False

    try:
        import PIL.Image  # @UnusedImport
        has_pil = True
    
    except ImportError:
        has_pil = False

    try:
        import pycurl  # @UnusedImport
        has_pycurl = True
    
    except ImportError:
        has_pycurl = False

    try:
        import pytz  # @UnusedImport
        has_pytz = True
    
    except ImportError:
        has_pytz = False

    import mediafiles
    has_ffmpeg = mediafiles.find_ffmpeg() is not None
    
    import motionctl
    has_motion = motionctl.find_motion() is not None
    
    import v4l2ctl
    has_v4lutils = v4l2ctl.find_v4l2_ctl() is not None
    
    has_mount_cifs = smbctl.find_mount_cifs() is not None
    
    ok = True
    if not has_tornado:
        print('please install tornado (python-tornado), version 3.1 or greater')
        ok = False
    
    if not has_jinja2:
        print('please install jinja2 (python-jinja2)')
        ok = False

    if not has_pil:
        print('please install PIL (python-imaging)')
        ok = False

    if not has_pycurl:
        print('please install pycurl (python-pycurl)')
        ok = False
    
    if not has_pytz:
        print('please install pytz (python-pytz)')
        ok = False
    
    if not has_ffmpeg:
        print('please install ffmpeg')
        ok = False

    if not has_motion:
        print('please install motion')
        ok = False

    if not has_v4lutils:
        print('please install v4l-utils')
        ok = False

    if settings.SMB_SHARES and not has_mount_cifs:
        print('please install cifs-utils')
        ok = False

    return ok

        
def _configure_signals():
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


def _configure_logging():
    logging.basicConfig(filename=None, level=settings.LOG_LEVEL,
            format='%(asctime)s: %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    
    logging.getLogger('tornado').setLevel(logging.WARN)


def _configure_tornado():
    AsyncHTTPClient.configure('tornado.curl_httpclient.CurlAsyncHTTPClient', max_clients=16)


def _print_help():
    print('Usage: ' + sys.argv[0] + ' [option1 value1] ...')
    print('available options: ')
    
    options = list(inspect.getmembers(settings))
    
    print('    --settings <module>')
    
    for (name, value) in sorted(options):
        if name.upper() != name:
            continue
        
        if not re.match('^[A-Z0-9_]+$', name):
            continue
        
        name = '--' + name.lower().replace('_', '-')
        if value is not None:
            value = type(value).__name__
        
        line = '    ' + name
        if value:
            line += ' <' + value + '>'
        print(line)
    
    print('')


def _run_server():
    import cleanup
    import motionctl
    import thumbnailer
    import tornado.ioloop
    import server

    server.application.listen(settings.PORT, settings.LISTEN)
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


def _start_motion():
    import tornado.ioloop
    import config
    import motionctl

    ioloop = tornado.ioloop.IOLoop.instance()
    
    # add a motion running checker
    def checker():
        if ioloop._stopped:
            return
            
        if not motionctl.running() and motionctl.started() and config.has_local_enabled_cameras():
            try:
                logging.error('motion not running, starting it')
                motionctl.start()
            
            except Exception as e:
                logging.error('failed to start motion: %(msg)s' % {
                        'msg': unicode(e)}, exc_info=True)

        ioloop.add_timeout(datetime.timedelta(seconds=settings.MOTION_CHECK_INTERVAL), checker)
    
    motionctl.start()
        
    ioloop.add_timeout(datetime.timedelta(seconds=settings.MOTION_CHECK_INTERVAL), checker)


def _start_cleanup():
    import cleanup

    cleanup.start()
    logging.info('cleanup started')


def _start_wsswitch():
    import wsswitch

    wsswitch.start()
    logging.info('wsswitch started')


def _start_thumbnailer():
    import thumbnailer

    thumbnailer.start()
    logging.info('thumbnailer started')


if __name__ == '__main__':
    cmd = _configure_settings()
    
    import smbctl

    if not _test_requirements():
        sys.exit(-1)
    
    _configure_signals()
    _configure_logging()
    _configure_tornado()
    
    if settings.SMB_SHARES:
        stop, start = smbctl.update_mounts()
        if start:
            _start_motion()

    else:
        _start_motion()
        
    _start_cleanup()
    _start_wsswitch()
    
    if settings.THUMBNAILER_INTERVAL:
        _start_thumbnailer()

    _run_server()
