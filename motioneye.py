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
import inspect
import logging
import os.path
import re
import signal
import sys

import settings

sys.path.append(os.path.join(settings.PROJECT_PATH, 'src'))

VERSION = '0.8'


def _test_requirements():
    
    try:
        import tornado  # @UnusedImport
        tornado = True
    
    except ImportError:
        tornado = False

    try:
        import jinja2  # @UnusedImport
        jinja2 = True
    
    except ImportError:
        jinja2 = False

    try:
        import PIL.Image  # @UnusedImport
        pil = True
    
    except ImportError:
        pil = False

    import mediafiles
    ffmpeg = mediafiles.find_ffmpeg() is not None
    
    import motionctl
    motion = motionctl.find_motion() is not None
    
    import v4l2ctl
    v4lutils = v4l2ctl.find_v4l2_ctl() is not None
    
    ok = True
    if not tornado:
        print('please install tornado (python-tornado)')
        ok = False
    
    if not jinja2:
        print('please install jinja2 (python-jinja2)')
        ok = False

    if not pil:
        print('please install PIL (python-imaging)')
        ok = False

    if not ffmpeg:
        print('please install ffmpeg')
        ok = False

    if not motion:
        print('please install motion')
        ok = False

    if not v4lutils:
        print('please install v4l-utils')
        ok = False

    return ok

        
def _configure_signals():
    def bye_handler(signal, frame):
        import tornado.ioloop
        import motionctl
        
        logging.info('interrupt signal received, shutting down...')

        # shut down the IO loop if it has been started
        ioloop = tornado.ioloop.IOLoop.instance()
        if ioloop.running():
            ioloop.stop()
        
        logging.info('server stopped')
        
        if motionctl.running():
            motionctl.stop()
            logging.info('motion stopped')

    signal.signal(signal.SIGINT, bye_handler)
    signal.signal(signal.SIGTERM, bye_handler)
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)


def _configure_logging():
    logging.basicConfig(filename=None, level=settings.LOG_LEVEL,
            format='%(asctime)s: %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')


def _configure_settings():
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


def _print_help():
    print('Usage: ' + sys.argv[0] + ' [option1 value1] ...')
    print('available options: ')
    
    options = list(inspect.getmembers(settings))
    options.append(('THUMBNAILS', None))
    
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


def _do_thumbnails():
    import config
    import mediafiles
    
    logging.info('recreating thumbnails for all video files...')
    
    for camera_id in config.get_camera_ids():
        camera_config = config.get_camera(camera_id)
        if camera_config.get('@proto') != 'v4l2':
            continue
        
        logging.info('listing movie files for camera %(name)s' % {
                'name': camera_config['@name']})
        
        target_dir = camera_config['target_dir']
        
        for (full_path, st) in mediafiles._list_media_files(target_dir, mediafiles._MOVIE_EXTS):  # @UnusedVariable
            mediafiles.make_movie_preview(camera_config, full_path)
    
    logging.info('done.')


def _start_server():
    import tornado.ioloop
    import server

    server.application.listen(settings.PORT, settings.LISTEN)
    logging.info('server started')
    
    tornado.ioloop.IOLoop.instance().start()


def _start_motion():
    import tornado.ioloop
    import config
    import motionctl

    # add a motion running checker
    def checker():
        ioloop = tornado.ioloop.IOLoop.instance()
        if ioloop._stopped:
            return
            
        if not motionctl.running() and config.has_enabled_cameras():
            try:
                motionctl.start()
                logging.info('motion started')
            
            except Exception as e:
                logging.error('failed to start motion: %(msg)s' % {
                        'msg': unicode(e)})

        ioloop.add_timeout(datetime.timedelta(seconds=settings.MOTION_CHECK_INTERVAL), checker)
    
    checker()


def _start_cleanup():
    import tornado.ioloop
    import mediafiles

    ioloop = tornado.ioloop.IOLoop.instance()
    
    def do_cleanup():
        if ioloop._stopped:
            return
        
        try:
            mediafiles.cleanup_media('picture')
            mediafiles.cleanup_media('movie')
            
        except Exception as e:
            logging.error('failed to cleanup media files: %(msg)s' % {
                    'msg': unicode(e)})

        ioloop.add_timeout(datetime.timedelta(seconds=settings.CLEANUP_INTERVAL), do_cleanup)

    ioloop.add_timeout(datetime.timedelta(seconds=settings.CLEANUP_INTERVAL), do_cleanup)


def _start_movie_thumbnailer():
    import tornado.ioloop
    import mediafiles

    ioloop = tornado.ioloop.IOLoop.instance()
    
    def do_next_movie_thumbail():
        if ioloop._stopped:
            return
        
        try:
            mediafiles.make_next_movie_preview()
            
        except Exception as e:
            logging.error('failed to make movie thumbnail: %(msg)s' % {
                    'msg': unicode(e)})

        ioloop.add_timeout(datetime.timedelta(seconds=settings.THUMBNAILER_INTERVAL), do_next_movie_thumbail)
    
    ioloop.add_timeout(datetime.timedelta(seconds=settings.THUMBNAILER_INTERVAL), do_next_movie_thumbail)


if __name__ == '__main__':
    if not _test_requirements():
        sys.exit(01)
    
    cmd = _configure_settings()
    _configure_signals()
    _configure_logging()
    
    if cmd:
        if cmd == 'thumbnails':
            _do_thumbnails()
        
        else:
            print('unknown command line option: ' + cmd)
            sys.exit(-1)
        
        sys.exit(0)
    
    _start_motion()
    _start_cleanup()
    _start_movie_thumbnailer()
    _start_server()
