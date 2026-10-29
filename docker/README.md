# Docker instructions

## Running from the official images

The easiest way to run motionEye under docker is to use the official images.
The command below will run motionEye and preserve your configuration and videos
across motionEye restarts.

```bash
docker pull motioneyeproject/motioneye
docker run \
  --rm \
  -d \
  -p 8765:8765 \
  --hostname="motioneye" \
  -v /etc/localtime:/etc/localtime:ro \
  -v /data/motioneye/config:/etc/motioneye \
  -v /data/motioneye/videos:/var/lib/motioneye \
  motioneyeproject/motioneye
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
docker pull motioneyeproject/motioneye
docker run \
  --rm \
  -d \
  -p 8765:8765 \
  --hostname="motioneye" \
  -v /etc/localtime:/etc/localtime:ro \
  --mount type=volume,source=motioneye-config,destination=/etc/motioneye \
  --mount type=volume,source=motioneye-videos,destination=/var/lib/motioneye \
  motioneyeproject/motioneye
```

Use `docker volume ls` to view existing volumes.

## Running as a non-root user

By default, motionEye and motion run as root inside the container, hence their
files in the volumes are owned by root on the host. To run them as another user
and group instead, pass their numeric IDs with `--user`, for example those of
your login user. The user does not need to exist inside the container. To
access camera devices like `/dev/video0`, also add the group which owns them:

```bash
docker run \
  --user "$(id -u):$(id -g)" \
  --group-add video \
  ...
```

The config and media directories or volumes must be writable by that user. For
directories on the host, create them with that owner before the first start:

```bash
mkdir -p /data/motioneye/config /data/motioneye/videos
chown "$(id -u):$(id -g)" /data/motioneye/config /data/motioneye/videos
```

For docker volumes, change their owner once with a container which runs as root:

```bash
docker run \
  --rm \
  --entrypoint chown \
  --mount type=volume,source=motioneye-config,destination=/etc/motioneye \
  --mount type=volume,source=motioneye-videos,destination=/var/lib/motioneye \
  motioneyeproject/motioneye \
  "$(id -u):$(id -g)" /etc/motioneye /var/lib/motioneye
```

When switching an existing installation from root to another user, change the
owner of the files inside as well, with `chown -R`.

## Building your own image

It's also possible to build your own motionEye docker image:

```bash
TIMESTAMP="$(date '+%Y%m%d-%H%M')"

cd /tmp && \
git clone https://github.com/motioneye-project/motioneye.git && \
cd motioneye && \
docker build \
  --network host \
  -t "${USER?}/motioneye:${TIMESTAMP}" \
  --no-cache \
  -f docker/Dockerfile .
```

This will create a local image called `your_username/motioneye:YYYYMMDD-HHMM`.
You can run this image using the examples under "Running from the official images", but
omitting the `docker pull` command and replacing
`motioneyeproject/motioneye` with the name of the local image you just built.
