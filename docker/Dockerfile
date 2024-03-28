FROM debian:bookworm-slim
LABEL maintainer="Marcus Klein <himself@kleini.org>"

# By default, run as root
ARG RUN_UID=0
ARG RUN_GID=0

COPY . /tmp/motioneye
COPY docker/entrypoint.sh /entrypoint.sh

# Build deps:
# - armhf: Python headers, C compiler and libjpeg for Pillow, until piwheels provides the latest version: https://piwheels.org/project/pillow/
# - other: Python headers, C compiler, libcurl and libssl for pycurl: https://pypi.org/project/pycurl/#files
RUN printf '%b' '[global]\nbreak-system-packages=true\n' > /etc/pip.conf && \
    case "$(dpkg --print-architecture)" in \
      'armhf') PACKAGES='python3-dev gcc libjpeg62-turbo-dev'; printf '%b' 'extra-index-url=https://www.piwheels.org/simple/\n' >> /etc/pip.conf;; \
      *) PACKAGES='python3-dev gcc libcurl4-openssl-dev libssl-dev';; \
    esac && \
    apt-get -q update && \
    DEBIAN_FRONTEND="noninteractive" apt-get -qq --option Dpkg::Options::="--force-confnew" --no-install-recommends install \
      ca-certificates curl python3 fdisk $PACKAGES && \
    curl -sSfO 'https://bootstrap.pypa.io/get-pip.py' && \
    python3 get-pip.py && \
    python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel && \
    python3 -m pip install --no-cache-dir /tmp/motioneye && \
    motioneye_init --skip-systemd --skip-apt-update && \
    # Change uid/gid of user/group motion to match our desired IDs. This will
    # make it easier to use execute motion as our desired user later.
    sed -i "s/^\(motion:[^:]*\):[0-9]*:[0-9]*:\(.*\)/\1:${RUN_UID}:${RUN_GID}:\2/" /etc/passwd && \
    sed -i "s/^\(motion:[^:]*\):[0-9]*:\(.*\)/\1:${RUN_GID}:\2/" /etc/group && \
    mv /etc/motioneye/motioneye.conf /etc/motioneye.conf.sample && \
    mkdir /var/log/motioneye /var/lib/motioneye && \
    chown motion:motion /var/log/motioneye /var/lib/motioneye && \
    # Cleanup
    python3 -m pip uninstall -y pip setuptools wheel && \
    DEBIAN_FRONTEND="noninteractive" apt-get -qq autopurge $PACKAGES && \
    apt-get clean && \
    rm -r /var/lib/apt/lists /var/cache/apt /tmp/motioneye get-pip.py /root/.cache

# R/W needed for motionEye to update configurations
VOLUME /etc/motioneye

# Video & images
VOLUME /var/lib/motioneye

EXPOSE 8765

ENTRYPOINT ["/entrypoint.sh"]
