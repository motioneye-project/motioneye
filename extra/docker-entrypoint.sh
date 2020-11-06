#!/bin/sh

test -e /etc/motioneye/motioneye.conf || \
	cp /usr/share/motioneye/extra/motioneye.conf.sample /etc/motioneye/motioneye.conf

exec /usr/bin/tini /usr/local/bin/meyectl -- startserver -c /etc/motioneye/motioneye.conf