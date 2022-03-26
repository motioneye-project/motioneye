# Docker instructions

## Running from the official images

The easiest way to run motionEye under docker is to use the official images.
The command below will run motionEye and preserve your configuration and videos
across motionEye restarts.

```bash
docker pull ccrisan/motioneye:master-amd64
docker run \
  --rm \
  -d \
  -p 8765:8765 \
  --hostname="motioneye" \
  -v /etc/localtime:/etc/localtime:ro \
  -v /data/motioneye/config:/etc/motioneye \
  -v /data/motioneye/videos:/var/lib/motioneye \
  ccrisan/motioneye:master-amd64
```

This configuration maps motionEye configs into the `/data/motioneye/config`
directory on the host. Videos will be saved under `/data/motioneye/videos`.
Change the directories to suit your particular needs and make sure those
directories exist on the host before you start the container.

Some may prefer to use docker volumes instead of mapped directories on the
host. You can easily accomplish this by using the commands below:

```bash
docker volume create motioneye-config
docker volume create motioneye-videos
docker pull ccrisan/motioneye:master-amd64
docker run \
  --rm \
  -d \
  -p 8765:8765 \
  --hostname="motioneye" =
  -v /etc/localtime:/etc/localtime:ro \
  --mount type=volume,source=motioneye-config,destination=/etc/motioneye \
  --mount type=volume,source=motioneye-videos,destination=/var/lib/motioneye \
  ccrisan/motioneye:master-amd64
```

Use `docker volume ls` to view existing volumes.

## Building your own image

It's also possible to build your own motionEye docker image. This allows the
use of UIDs other than root for the `motion` and `meyectl` daemons (the default
on official images). If you want to use a non-privileged user/group for
motionEye, *please make sure that user/group exist on the host* before running
the commands below.

For the examples below, we assume user `motion` and group `motion` exist on the host server.

```bash
RUN_USER="motion"
RUN_UID=$(id -u ${RUN_USER})
RUN_GID=$(id -g ${RUN_USER})
TIMESTAMP="$(date '+%Y%m%d-%H%M')"

cd /tmp && \
git clone https://github.com/motioneye-project/motioneye.git && \
cd motioneye && \
docker build \
  --network host \
  --build-arg="RUN_UID=${RUN_UID?}" \
  --build-arg="RUN_GID=${RUN_GID?}" \
  -t "${USER?}/motioneye:${TIMESTAMP}" \
  --no-cache \
  -f extra/Dockerfile .
```

This will create a local image called `your_username/motioneye:YYYYMMDD-HHMM`.
You can run this image using the examples under "Running official images", but
omitting the `docker pull` command and replacing
`ccrisan/motioneye:master-amd64` with the name of the local image you just built.
