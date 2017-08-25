FROM ubuntu:17.04
LABEL maintainer="Conor Heine <conor.heine@gmail.com>"

RUN apt-get --quiet update && \
    DEBIAN_FRONTEND="noninteractive" apt-get --quiet --yes --option Dpkg::Options::="--force-confnew" --no-install-recommends install \
    automake \
    autoconf \
    build-essential \
    ffmpeg \
    git \
    libav-tools \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libcurl4-openssl-dev \
    libjpeg-dev \
    libssl-dev \
    libswscale-dev \
    pkgconf \
    python-dev \
    python-pip \
    python-setuptools \
    subversion \
    v4l-utils && \
    apt-get --quiet autoremove && \
    apt-get --quiet --yes clean && rm -rf /var/lib/apt/lists/* && rm -f /var/cache/apt/*.bin

# Pip
RUN pip install tornado jinja2 pillow pycurl

RUN cd /tmp && git clone --branch 4.0 https://github.com/Motion-Project/motion.git motion-project
RUN cd /tmp/motion-project && \
    autoreconf -fiv && \
    ./configure --prefix=/usr --without-pgsql --without-sqlite3 --without-mysql --with-ffmpeg=/usr && \
    make && \
    touch README \
    make install && \
    cp motion /usr/local/bin/motion && cd / && \
    rm -rf /tmp/motion-project

RUN pip install motioneye

# R/W needed for motioneye to update configurations
VOLUME /etc/motioneye

# PIDs
VOLUME /var/run/motion

# Video & images
VOLUME /var/lib/motioneye

ADD motioneye.conf.sample /usr/share/motioneye/extra/

CMD test -e /etc/motioneye/motioneye.conf || \    
    cp /usr/share/motioneye/extra/motioneye.conf.sample /etc/motioneye/motioneye.conf ; \
    /usr/local/bin/meyectl startserver -c /etc/motioneye/motioneye.conf

EXPOSE 8765
