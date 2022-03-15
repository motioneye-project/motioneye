FROM debian:bullseye-slim
LABEL maintainer="Marcus Klein <himself@kleini.org>"

# By default, run as root.
ARG RUN_UID=0
ARG RUN_GID=0

COPY . /tmp/motioneye

RUN apt-get update && \
    DEBIAN_FRONTEND="noninteractive" apt-get --yes --option Dpkg::Options::="--force-confnew" --no-install-recommends install \
      ffmpeg \
      motion \
      python3-pip \
      python3-tornado \
      python3-jinja2 \
      python3-pil \
      python3-pycurl \
      python3-babel \
      python3-numpy \
      python3-boto3 \
      tzdata \
      v4l-utils && \
    # Change uid/gid of user/group motion to match our desired IDs.  This will
    # make it easier to use execute motion as our desired user later.
    sed -i -e "s/^\(motion:[^:]*\):[0-9]*:[0-9]*:\(.*\)/\1:${RUN_UID}:${RUN_GID}:\2/" /etc/passwd && \
    sed -i -e "s/^\(motion:[^:]*\):[0-9]*:\(.*\)/\1:${RUN_GID}:\2/" /etc/group && \
    pip install /tmp/motioneye && \
    # Cleanup
    rm -rf motioneye && \
    apt-get --yes purge python3-pip && \
    apt-get --yes autopurge && \
    apt-get --yes clean && rm -rf /var/lib/apt/lists/* && rm -f /var/cache/apt/*.bin

COPY motioneye/extra/motioneye.conf.sample /usr/share/motioneye/extra/motioneye.conf.sample

# R/W needed for motioneye to update configurations
VOLUME /etc/motioneye

# Video & images
VOLUME /var/lib/motioneye

EXPOSE 8765

ENTRYPOINT ["/entrypoint.sh"]
