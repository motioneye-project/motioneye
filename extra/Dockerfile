FROM debian:buster-slim
LABEL maintainer="Marcus Klein <himself@kleini.org>"

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

COPY . /tmp/motioneye

RUN echo "deb http://snapshot.debian.org/archive/debian/20200630T024205Z sid main contrib non-free" >>/etc/apt/sources.list && \
    apt-get update && \
    DEBIAN_FRONTEND="noninteractive" apt-get -t stable --yes --option Dpkg::Options::="--force-confnew" --no-install-recommends install \
    curl \
    ffmpeg \
    libmicrohttpd12 \
    libpq5 \
    lsb-release \
    mosquitto-clients \
    python3-jinja2 \
    python3-pil \
    python3-pip \
    python3-pycurl \
    python3-setuptools \
    python3-six \
    python3-tornado \
    python3-tz \
    python3-wheel \
    tzdata \
    v4l-utils && \
    pip3 install /tmp/motioneye && \
    rm -rf /tmp/motioneye && \
    DEBIAN_FRONTEND="noninteractive" apt-get -t sid --yes --option Dpkg::Options::="--force-confnew" --no-install-recommends install \
      motion \
      libmysqlclient21 && \
    apt-get purge --yes \
    python3-pip \
    python3-setuptools \
    python3-wheel && \
    apt-get autoremove --yes && \
    apt-get --yes clean && rm -rf /var/lib/apt/lists/* && rm -f /var/cache/apt/*.bin

# R/W needed for motioneye to update configurations
VOLUME /etc/motioneye

# PIDs
VOLUME /var/run/motion

# Video & images
VOLUME /var/lib/motioneye

ADD extra/motioneye.conf.sample /usr/share/motioneye/extra/

CMD test -e /etc/motioneye/motioneye.conf || \
    cp /usr/share/motioneye/extra/motioneye.conf.sample /etc/motioneye/motioneye.conf ; \
    /usr/local/bin/meyectl startserver -c /etc/motioneye/motioneye.conf

EXPOSE 8765
