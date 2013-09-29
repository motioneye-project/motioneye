#!/usr/bin/env python2

import logging
import os.path
import signal
import sys
import tornado.ioloop

import settings
sys.path.append(os.path.join(settings.PROJECT_PATH, 'src'))

import server


def _configure_signals():
    def bye_handler(signal, frame):
        logging.info('interrupt signal received, shutting down...')

        # shut down the IO loop if it has been started
        ioloop = tornado.ioloop.IOLoop.instance()
        if ioloop.running():
            ioloop.stop()
        
        logging.info('server stopped')

    signal.signal(signal.SIGINT, bye_handler)
    signal.signal(signal.SIGTERM, bye_handler)
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)


def _configure_logging():
    logging.basicConfig(filename=None, level=settings.LOG_LEVEL,
            format='%(asctime)s: %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')


def _start_server():
    server.application.listen(settings.PORT, settings.LISTEN)
    logging.info('server started')
    
    tornado.ioloop.IOLoop.instance().start()


if __name__ == '__main__':
    _configure_signals()
    _configure_logging()
    _start_server()
    
#     import config # TODO remove this
#     main_config = config.get_main()
#     config.add_camera('v4l2:///dev/video0')
#     #data = config.get_camera(1)
#     #data['@enabled'] = True
#     #config.set_camera(1, data)
#     config.rem_camera(1)
    
#     import motionctl
#     motionctl.start()
