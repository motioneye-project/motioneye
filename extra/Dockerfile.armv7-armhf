FROM multiarch/debian-debootstrap:armhf-stretch
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
ENV LD_LIBRARY_PATH /opt/vc/lib

RUN apt-get --quiet update && \
    apt-get --quiet upgrade --yes && \
    DEBIAN_FRONTEND="noninteractive" apt-get --quiet --yes --option Dpkg::Options::="--force-confnew" --no-install-recommends install \
    curl \
    ffmpeg \
    git \
    libmariadbclient18 \
    libpq5 \
    lsb-release \
    python-jinja2 \
    python-pil \
    python-pip \
    python-pycurl \
    python-setuptools \
    python-tornado \
    python-wheel \
    v4l-utils \
    zlib1g-dev && \
    git clone --depth 1 https://github.com/Hexxeh/rpi-firmware.git /tmp/rpi-firmware && \
    cp -rv /tmp/rpi-firmware/vc/hardfp/opt/vc /opt && \
    rm -rf /tmp/rpi-firmware && \
    curl -L --output /tmp/motion.deb https://github.com/Motion-Project/motion/releases/download/release-4.1/pi_stretch_motion_4.1-1_armhf.deb && \
    dpkg -i /tmp/motion.deb && \
    rm /tmp/motion.deb && \
    pip install /tmp/motioneye && \
    rm -rf /tmp/motioneye && \
    apt-get purge --yes \
    git \
    python-pip \
    python-setuptools \
    python-wheel && \
    apt-get --quiet autoremove --yes && \
    apt-get --quiet --yes clean && rm -rf /var/lib/apt/lists/* && rm -f /var/cache/apt/*.bin

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
