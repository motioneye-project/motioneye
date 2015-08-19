
import logging
import os.path
import sys

import motioneye

# the root directory of the project
PROJECT_PATH = os.path.dirname(motioneye.__file__)

# the templates directory
TEMPLATE_PATH = os.path.join(PROJECT_PATH, 'templates')

# the static files directory
STATIC_PATH = os.path.join(PROJECT_PATH, 'static')

# static files (.css, .js etc) are served at this root url
STATIC_URL = '/static/'

# path to the config directory; must be writable
CONF_PATH = [sys.prefix, ''][sys.prefix == '/usr']  + '/etc/motioneye'

# pid files go here
for d in ['/run', '/var/run', '/tmp', '/var/tmp']:
    if os.path.exists(d):
        RUN_PATH = d
        break
    
else:
    RUN_PATH = PROJECT_PATH

# log files go here
for d in ['/log', '/var/log', '/tmp', '/var/tmp']:
    if os.path.exists(d):
        LOG_PATH = d
        break
    
else:
    LOG_PATH = RUN_PATH

# default output path for media files
MEDIA_PATH = RUN_PATH

# path to motion binary (automatically detected if not set)
MOTION_BINARY = None

# the log level
LOG_LEVEL = logging.INFO

# IP addresses to listen on
LISTEN = '0.0.0.0'

# the TCP port to listen on
PORT = 8765

# interval in seconds at which motionEye checks the SMB mounts
MOUNT_CHECK_INTERVAL = 300

# interval in seconds at which motionEye checks if motion is running
MOTION_CHECK_INTERVAL = 10

# interval in seconds at which the janitor is called to remove old pictures and movies
CLEANUP_INTERVAL = 43200

# interval in seconds at which the thumbnail mechanism runs (set to 0 to disable) 
THUMBNAILER_INTERVAL = 60

# timeout in seconds when waiting for response from a remote motionEye server
REMOTE_REQUEST_TIMEOUT = 10

# timeout in seconds when waiting for mjpg data from the motion daemon
MJPG_CLIENT_TIMEOUT = 10

# timeout in seconds after which an idle mjpg client is removed (set to 0 to disable)
MJPG_CLIENT_IDLE_TIMEOUT = 10

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

# enable adding and removing cameras from UI
ADD_REMOVE_CAMERAS = True
