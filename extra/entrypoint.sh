#!/usr/bin/env sh
test -e /etc/motioneye/motioneye.conf || \
cp /usr/share/motioneye/extra/motioneye.conf.sample /etc/motioneye/motioneye.conf ; \
# We need to chown at startup time since volumes are mounted as root. This is fugly.
mkdir -p /var/run/motioneye /var/log/motioneye ; \
chown motion:motion /var/run /var/run/motioneye /var/log /etc/motioneye /var/lib/motioneye /var/log/motioneye /usr/share/motioneye/extra ; \
su -g motion motion -s /bin/bash -c "LANGUAGE=en /usr/local/bin/meyectl startserver -c /etc/motioneye/motioneye.conf"
