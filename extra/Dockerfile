
FROM ubuntu:15.04
MAINTAINER Conor Heine <conor.heine@gmail.com>

ENV DEBIAN_FRONTEND noninteractive
ENV export LANGUAGE=en_US.UTF-8
ENV export LC_ALL=en_US.UTF-8
ENV export LANG=en_US.UTF-8
ENV export LC_TYPE=en_US.UTF-8

RUN apt-get update

# Core
RUN apt-get --yes install \
        git \
        motion \
        ffmpeg \
        v4l-utils \
        python-pip \
        libssl-dev \
        libjpeg-dev \
        libcurl4-openssl-dev

 # Python
RUN apt-get --yes install \
        python2.7 \
        python-setuptools \
        python-dev \
        python-pip

# Pip
RUN pip install tornado jinja2 pillow pycurl

# Fetch motioneye src
RUN cd /tmp && git clone https://github.com/ccrisan/motioneye.git && \
    cd /tmp/motioneye && python setup.py install && mkdir /etc/motioneye && \
    cp /tmp/motioneye/extra/motioneye.conf.sample /etc/motioneye/motioneye.conf && \
    rm -rf /tmp/*


# R/W needed for motioneye to update configurations
VOLUME /etc/motioneye

# PIDs
VOLUME /var/run/motion

# Video & images
VOLUME /var/lib/motion

CMD /usr/local/bin/meyectl startserver -c /etc/motioneye/motioneye.conf
EXPOSE 8765

