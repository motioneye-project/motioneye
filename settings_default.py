
import logging
import os.path
import sys


PROJECT_PATH = os.path.dirname(sys.argv[0])
CONF_PATH = os.path.join(PROJECT_PATH, 'conf')
RUN_PATH = PROJECT_PATH

DEBUG = True
LOG_LEVEL = logging.DEBUG

TEMPLATE_PATH = os.path.join(PROJECT_PATH, 'templates')

STATIC_PATH = os.path.join(PROJECT_PATH, 'static')
STATIC_URL = '/static/'

LISTEN = '0.0.0.0'
PORT = 8765

MOTION_CHECK_INTERVAL = 10
CLEANUP_INTERVAL = 43200
