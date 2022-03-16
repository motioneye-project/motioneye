#!/usr/bin/env sh
# We need to chown at startup time since volumes are mounted as root. This is fugly.
mkdir -p /run/motioneye
chown motion:motion /run/motioneye
[ -f '/etc/motioneye/motioneye.conf' ] || cp -a /etc/motioneye.conf.sample /etc/motioneye/motioneye.conf
exec su -g motion motion -s /bin/dash -c "LANGUAGE=en exec /usr/local/bin/meyectl startserver -c /etc/motioneye/motioneye.conf"
