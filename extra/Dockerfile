FROM ubuntu:17.04
LABEL maintainer="Conor Heine <conor.heine@gmail.com>"

RUN apt-get --quiet update && \
    DEBIAN_FRONTEND="noninteractive" apt-get --quiet --yes --option Dpkg::Options::="--force-confnew" --no-install-recommends install \
    gcc \
    ffmpeg \
    libcurl4-openssl-dev \
    libssl-dev \
    motion \
    python-dev \
    python-pip \
    python-setuptools \
    python-wheel \
    v4l-utils && \
    apt-get --quiet autoremove && \
    apt-get --quiet --yes clean && rm -rf /var/lib/apt/lists/* && rm -f /var/cache/apt/*.bin

# Pip
RUN pip install tornado jinja2 pillow pycurl

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
