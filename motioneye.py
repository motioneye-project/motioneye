#!/usr/bin/env python2

import inspect
import logging
import os.path
import re
import signal
import sys
import tornado.ioloop

import settings

sys.path.append(os.path.join(settings.PROJECT_PATH, 'src'))


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

    if not motionctl.running() and config.has_enabled_cameras():
        motionctl.start()
        logging.info('motion started')


if __name__ == '__main__':
    _configure_settings()
    _configure_signals()
    _configure_logging()
    _start_motion()
    _start_server()
