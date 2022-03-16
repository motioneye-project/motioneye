FROM debian:bullseye-slim
LABEL maintainer="Marcus Klein <himself@kleini.org>"

# By default, run as root
ARG RUN_UID=0
ARG RUN_GID=0

COPY . /tmp/motioneye

RUN case "$(dpkg --print-architecture)" in \
      'armhf') PACKAGES=''; printf '%b' '[global]\nextra-index-url=https://www.piwheels.org/simple/\n' > /etc/pip.conf;; \
      *) PACKAGES='python3-dev libcurl4-openssl-dev gcc libssl-dev';; \
    esac && \
    apt-get update && \
    DEBIAN_FRONTEND="noninteractive" apt-get -y --option Dpkg::Options::="--force-confnew" --no-install-recommends install \
      python3 python3-pip $PACKAGES tzdata && \
    # Change uid/gid of user/group motion to match our desired IDs. This will
    # make it easier to use execute motion as our desired user later.
    sed -i "s/^\(motion:[^:]*\):[0-9]*:[0-9]*:\(.*\)/\1:${RUN_UID}:${RUN_GID}:\2/" /etc/passwd && \
    sed -i "s/^\(motion:[^:]*\):[0-9]*:\(.*\)/\1:${RUN_GID}:\2/" /etc/group && \
    pip3 install --no-cache-dir /tmp/motioneye && \
    motioneye_init --skip-systemd --skip-apt-update && \
    mv /etc/motioneye/motioneye.conf /etc/motioneye.conf.sample && \
    mkdir /var/log/motioneye /var/lib/motioneye && \
    chown motion:motion /var/log/motioneye /var/lib/motioneye && \
    # Cleanup
    DEBIAN_FRONTEND="noninteractive" apt-get -y autopurge python3-pip $PACKAGES && \
    apt-get clean && \
    rm -r /var/lib/apt/lists /var/cache/apt /tmp/motioneye

# R/W needed for motionEye to update configurations
VOLUME /etc/motioneye

# Video & images
VOLUME /var/lib/motioneye

EXPOSE 8765

ENTRYPOINT ["/entrypoint.sh"]
