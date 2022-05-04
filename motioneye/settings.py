import logging
import os.path
import socket
import sys

import motioneye

config_file = None

# interface language
lingvo = 'eo'

# available languages
langlist = [('en', 'English'), ('eo', 'esperanto'), ('fr', 'français')]

# gettext translation
traduction = None

# the root directory of the project
PROJECT_PATH = os.path.dirname(motioneye.__file__)

# the templates directory
TEMPLATE_PATH = os.path.join(PROJECT_PATH, 'templates')

# the static files directory
STATIC_PATH = os.path.join(PROJECT_PATH, 'static')

# path to the configuration directory (must be writable by motionEye)
CONF_PATH = [sys.prefix, ''][sys.prefix == '/usr'] + '/etc/motioneye'

# path to the directory where pid files go (must be writable by motionEye)
for d in ['/run', '/var/run', '/tmp', '/var/tmp']:
    if os.path.exists(d):
        RUN_PATH = d
        break

else:
    RUN_PATH = PROJECT_PATH

# path to the directory where log files go (must be writable by motionEye)
for d in ['/log', '/var/log', '/tmp', '/var/tmp']:
    if os.path.exists(d):
        LOG_PATH = d
        break

else:
    LOG_PATH = RUN_PATH

# default output path for media files (must be writable by motionEye)
MEDIA_PATH = '/var/lib/motioneye'

# the log level (use FATAL, ERROR, WARNING, INFO or DEBUG)
LOG_LEVEL = logging.INFO

# the IP address to listen on
# (0.0.0.0 for all interfaces, 127.0.0.1 for localhost)
LISTEN = '0.0.0.0'

# the TCP port to listen on
PORT = 8765

# path to the motion binary to use (automatically detected by default)
MOTION_BINARY = None

# whether motion HTTP control interface listens on
# localhost or on all interfaces
MOTION_CONTROL_LOCALHOST = True

# the TCP port that motion HTTP control interface listens on
MOTION_CONTROL_PORT = 7999

# interval in seconds at which motionEye checks if motion is running
MOTION_CHECK_INTERVAL = 10

# whether to restart the motion daemon when an error occurs while communicating with it
MOTION_RESTART_ON_ERRORS = False

# interval in seconds at which motionEye checks the SMB mounts
MOUNT_CHECK_INTERVAL = 300

# interval in seconds at which the janitor is called
# to remove old pictures and movies
CLEANUP_INTERVAL = 43200

# timeout in seconds to wait for response from a remote motionEye server
REMOTE_REQUEST_TIMEOUT = 10

# timeout in seconds to wait for mjpg data from the motion daemon
MJPG_CLIENT_TIMEOUT = 10

# timeout in seconds after which an idle mjpg client is removed
# (set to 0 to disable)
MJPG_CLIENT_IDLE_TIMEOUT = 10

# enable SMB shares (requires motionEye to run as root)
SMB_SHARES = False

# the directory where the SMB mount points will be created
SMB_MOUNT_ROOT = '/media'

# path to the wpa_supplicant.conf file
# (enable this to configure wifi settings from the UI)
WPA_SUPPLICANT_CONF = None

# path to the localtime file
# (enable this to configure the system time zone from the UI)
LOCAL_TIME_FILE = None

# enables shutdown and rebooting after changing system settings
# (such as wifi settings or time zone)
ENABLE_REBOOT = False

# enables motionEye version update (not implemented by default)
ENABLE_UPDATE = False

# timeout in seconds to use when talking to the SMTP server
SMTP_TIMEOUT = 60

# timeout in seconds to wait for media files list
LIST_MEDIA_TIMEOUT = 120

# timeout in seconds to wait for media files list, when sending emails
LIST_MEDIA_TIMEOUT_EMAIL = 10

# timeout in seconds to wait for media files list, when sending telegrams
LIST_MEDIA_TIMEOUT_TELEGRAM = 10

# timeout in seconds to wait for zip file creation
ZIP_TIMEOUT = 500

# timeout in seconds to wait for timelapse creation
TIMELAPSE_TIMEOUT = 500

# enable adding and removing cameras from UI
ADD_REMOVE_CAMERAS = True

# enable HTTPS certificate validation
VALIDATE_CERTS = True

# an external program to be executed whenever a password changes;
# the program will be invoked with environment variables MEYE_USERNAME and MEYE_PASSWORD
PASSWORD_HOOK = None

# enables HTTP basic authentication scheme (in addition to, not instead of the signature mechanism)
HTTP_BASIC_AUTH = False

# provides the possibility to override the hostname
SERVER_NAME = socket.gethostname()
