FROM debian:buster-slim
LABEL maintainer="Marcus Klein <himself@kleini.org>"

ARG MOTION_RELEASE=4.3.2
ARG BUILD_DATE
ARG VCS_REF
LABEL org.label-schema.build-date=$BUILD_DATE \
    org.label-schema.docker.dockerfile="extra/Dockerfile" \
    org.label-schema.license="GPLv3" \
    org.label-schema.name="motioneye" \
    org.label-schema.url="https://github.com/ccrisan/motioneye/wiki" \
    org.label-schema.vcs-ref=$VCS_REF \
    org.label-schema.vcs-type="Git" \
    org.label-schema.vcs-url="https://github.com/ccrisan/motioneye.git"

# default motion user is 101:101
ARG RUN_UID=101
ARG RUN_GID=101

RUN apt-get update && \
    DEBIAN_FRONTEND="noninteractive" apt-get --yes --no-install-recommends install \
      curl \
      ffmpeg \
      libmicrohttpd12 \
      libpq5 \
      lsb-release \
      mosquitto-clients \
      python-jinja2 \
      python-pil \
      python-pip \
      python-pip-whl \
      python-pycurl \
      python-setuptools \
      python-tornado \
      python-tz \
      python-wheel \
      tini \
      v4l-utils

RUN export TARGET=$(dpkg --print-architecture); \
    curl -LO https://github.com/Motion-Project/motion/releases/download/release-${MOTION_RELEASE}/buster_motion_${MOTION_RELEASE}-1_${TARGET}.deb && \
    apt-get -y install ./buster_motion_${MOTION_RELEASE}-1_${TARGET}.deb && \
    rm -f ./buster_motion_${MOTION_RELEASE}-1_${TARGET}.deb

COPY . /tmp/motioneye

RUN pip install /tmp/motioneye && \
    rm -rf /tmp/motioneye && \
    apt-get purge --yes python-setuptools python-wheel && \
    apt-get autoremove --yes && \
    apt-get --yes clean && rm -rf /var/lib/apt/lists/* && rm -f /var/cache/apt/*.bin

# Change uid/gid of user/group motion to match our desired IDs.  This will
# make it easier to use execute motion as our desired user later.
RUN sed -i -e "s/^\(motion:[^:]*\):[0-9]*:[0-9]*:\(.*\)/\1:${RUN_UID}:${RUN_GID}:\2/" /etc/passwd && \
    sed -i -e "s/^\(motion:[^:]*\):[0-9]*:\(.*\)/\1:${RUN_GID}:\2/" /etc/group

COPY extra/motioneye.conf.sample /usr/share/motioneye/extra/
COPY extra/docker-entrypoint.sh /docker-entrypoint.sh

# R/W needed for motioneye to update configurations
VOLUME /etc/motioneye

# Video & images
VOLUME /var/lib/motioneye

CMD test -e /etc/motioneye/motioneye.conf || \
    cp /usr/share/motioneye/extra/motioneye.conf.sample /etc/motioneye/motioneye.conf ; \
    # We need to chown at startup time since volumes are mounted as root. This is fugly.
    chown motion:motion /var/run /var/log /etc/motioneye /var/lib/motioneye /usr/share/motioneye/extra ; \
    su -g motion motion -s /bin/bash -c "/usr/local/bin/meyectl startserver -c /etc/motioneye/motioneye.conf"

EXPOSE 8765
