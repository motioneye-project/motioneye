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
import tornado.ioloop

import settings

sys.path.append(os.path.join(settings.PROJECT_PATH, 'src'))

VERSION = '0.1'


def _configure_signals():
    def bye_handler(signal, frame):
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
            print('unknown command line option: ' + arg)
            _print_help()
            sys.exit(-1)
    
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
    
    for (name, value) in sorted(inspect.getmembers(settings)):  # @UnusedVariable
        if name.upper() != name:
            continue
        
        if not re.match('^[A-Z0-9_]+$', name):
            continue
        
        name = '--' + name.lower().replace('_', '-')
        print('    ' + name)
    
    print('')
    

def _start_server():
    import server

    server.application.listen(settings.PORT, settings.LISTEN)
    logging.info('server started')
    
    tornado.ioloop.IOLoop.instance().start()


def _start_motion():
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
    import cleanup

    def do_cleanup():
        ioloop = tornado.ioloop.IOLoop.instance()
        if ioloop._stopped:
            return
        
        try:
            cleanup.cleanup_images()
            cleanup.cleanup_movies()
            
        except Exception as e:
            logging.error('failed to cleanup media files: %(msg)s' % {
                    'msg': unicode(e)})

        ioloop.add_timeout(datetime.timedelta(seconds=settings.CLEANUP_INTERVAL), do_cleanup)

    do_cleanup()


if __name__ == '__main__':
    _configure_settings()
    _configure_signals()
    _configure_logging()
    
    _start_motion()
    _start_cleanup()
    _start_server()
