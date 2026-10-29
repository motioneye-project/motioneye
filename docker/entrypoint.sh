#!/usr/bin/env sh
# motionEye runs as the user of the container: root, unless another one is given with "docker run --user"
# The settings may contain credentials (motion_control_authentication), hence nobody else may read them
set -e
[ -f '/etc/motioneye/motioneye.conf' ] || install -m 0600 /etc/motioneye.conf.sample /etc/motioneye/motioneye.conf
exec /usr/local/bin/meyectl startserver -c /etc/motioneye/motioneye.conf
