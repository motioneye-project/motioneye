#!/usr/bin/env python2

import logging
import motionctl
import os.path
import signal
import sys
import tornado.ioloop

import settings

sys.path.append(os.path.join(settings.PROJECT_PATH, 'src'))

import config
import server


def _configure_signals():
    def bye_handler(signal, frame):
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


def _start_server():
    server.application.listen(settings.PORT, settings.LISTEN)
    logging.info('server started')
    
    tornado.ioloop.IOLoop.instance().start()


def _start_motion():
    if not motionctl.running() and len(config.get_enabled_cameras()) > 0:
        motionctl.start()
        logging.info('motion started')


if __name__ == '__main__':
    _configure_signals()
    _configure_logging()
    _start_motion()
    _start_server()
