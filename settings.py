
import logging
import os.path
import sys


PROJECT_PATH = os.path.dirname(sys.argv[0])
#CONF_PATH = os.path.join(PROJECT_PATH, 'conf')
CONF_PATH = '/media/data/projects/motioneye/conf/'
RUN_PATH = '/media/data/projects/motioneye/'
#RUN_PATH = PROJECT_PATH

DEBUG = True
LOG_LEVEL = logging.DEBUG

TEMPLATE_PATH = os.path.join(PROJECT_PATH, 'templates')

STATIC_PATH = os.path.join(PROJECT_PATH, 'static')
STATIC_URL = '/static/'

LISTEN = '0.0.0.0'
PORT = 8765
