
import logging
import os.path
import sys

# you normally don't have to change these 
PROJECT_PATH = os.path.dirname(sys.argv[0])
TEMPLATE_PATH = os.path.join(PROJECT_PATH, 'templates')
STATIC_PATH = os.path.join(PROJECT_PATH, 'static')

# static files (.css, .js etc) are served at this root url
STATIC_URL = '/static/'

# path to the config directory; must be writable
CONF_PATH = os.path.abspath(os.path.join(PROJECT_PATH, 'conf'))

# pid files go here
RUN_PATH = os.path.abspath(os.path.join(PROJECT_PATH, 'run'))

# log files go here
LOG_PATH = os.path.abspath(os.path.join(PROJECT_PATH, 'log'))

# default output path for media files
MEDIA_PATH = os.path.abspath(os.path.join(PROJECT_PATH, 'media'))

# path to motion binary (automatically detected if not set)
MOTION_BINARY = None

# set to logging.DEBUG for verbose output
LOG_LEVEL = logging.INFO

# set to 127.0.0.1 to restrict access to localhost
LISTEN = '0.0.0.0'

# change the port according to your requirements/restrictions
PORT = 8765

# interval in seconds at which motionEye checks the SMB mounts
MOUNT_CHECK_INTERVAL = 300

# interval in seconds at which motionEye checks if motion is running
MOTION_CHECK_INTERVAL = 10

# interval in seconds at which the janitor is called to remove old pictures and movies
CLEANUP_INTERVAL = 43200

# interval in seconds at which the thumbnail mechanism runs (set to 0 to disable) 
THUMBNAILER_INTERVAL = 60

# timeout in seconds to wait for responses when contacting a remote server
REMOTE_REQUEST_TIMEOUT = 10

# timeout in seconds to wait for an access to a mjpg client before removing it
MJPG_CLIENT_TIMEOUT = 10

# the maximal number of entries per camera in the current pictures cache
PICTURE_CACHE_SIZE = 8

# the number of seconds that a cached picture is valid
PICTURE_CACHE_LIFETIME = 60

# enable SMB shares (requires root) 
SMB_SHARES = False

# the directory where the SMB mounts will be created
SMB_MOUNT_ROOT = '/media'

# path to a wpa_supplicant.conf file if wifi settings UI is desired
WPA_SUPPLICANT_CONF = None

# path to a localtime file if time zone settings UI is desired
LOCAL_TIME_FILE = None

# enables shutdown and rebooting after changing system settings (such as wifi settings or system updates)
ENABLE_REBOOT = False

# the timeout in seconds to use when talking to a SMTP server
SMTP_TIMEOUT = 60

# the time to wait for zip file creation
ZIP_TIMEOUT = 500
