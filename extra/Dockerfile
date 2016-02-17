
FROM ubuntu:15.04
MAINTAINER Conor Heine <conor.heine@gmail.com>

ENV DEBIAN_FRONTEND noninteractive
ENV export LANGUAGE=en_US.UTF-8
ENV export LC_ALL=en_US.UTF-8
ENV export LANG=en_US.UTF-8
ENV export LC_TYPE=en_US.UTF-8

RUN apt-get update && \
    apt-get --yes install \
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
    apt-get clean

# Pip
RUN pip install tornado jinja2 pillow pycurl

RUN cd /tmp && \
    git clone https://github.com/Mr-Dave/motion.git motion-mrdave && \
    cd /tmp/motion-mrdave && \
    autoreconf -fiv && \
    ./configure --prefix=/usr --without-pgsql --without-sdl --without-sqlite3 --without-mysql && \
    make && \
    make install && \
    cp motion /usr/local/bin/motion && \
    rm -rf /tmp/motion-mrdave

RUN cd /tmp && \
    git clone https://github.com/ccrisan/motioneye.git && \
    cd /tmp/motioneye && \
    python setup.py install && \
    mkdir /etc/motioneye && \
    mkdir -p /usr/share/motioneye/extra && \
    cp /tmp/motioneye/extra/motioneye.conf.sample /usr/share/motioneye/extra/motioneye.conf.sample && \
    rm -rf /tmp/motioneye

# R/W needed for motioneye to update configurations
VOLUME /etc/motioneye

# PIDs
VOLUME /var/run/motion

# Video & images
VOLUME /var/lib/motion

CMD /usr/local/bin/meyectl startserver -c /etc/motioneye/motioneye.conf
EXPOSE 8765

