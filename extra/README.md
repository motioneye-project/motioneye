motionEye comes with a `Dockerfile` and a sample `docker-compose.yml`, both in the `/extra` directory of the project (https://github.com/ccrisan/motioneye/tree/master/extra).

### Instructions
1. Download the `Dockerfile` and `docker-compose.yml` either by checking out the motioneye repository, or by downloading them directly from Github.

2. Build your motionEye Docker image from the `Dockerfile`. First `cd` into the directory where you put the `Dockerfile`. Then:

        # If you would like build docker image from official project
        docker build -t motioneye .

        # If you would like build docker image from forked project (ex: from badele github repository)
        docker build --build-arg GIT_REPOSITORY=https://github.com/badele/motioneye.git -t motioneye .
        
*Note:* If /etc/motioneye/motioneye.conf not exist, it's copied from /usr/share/motioneye/extra/motioneye.conf.sample (Not overwrite the volume)

3. Have a cup of coffee while the image builds :)

4. Either start a container using `docker run` or use the provided sample `docker-compose.yml` together with `docker-compose`.

#### With docker run:

        docker run -d --name=motioneye \
            --device=/dev/video0
            -p 8081:8081 \
            -p 8765:8765 \
            -e TIMEZONE="America/New_York" \
            -v /mnt/motioneye/media:/media \
            -v /mnt/motioneye/config:/etc/motioneye \
            --restart=always \
            motioneye

#### With docker-compose.yml:

Edit `docker-compose.yml` and modify the timezone to your own (A list is available at http://php.net/manual/en/timezones.php).

Also edit the two mount points to a directory in your system. Save the file, and then run:

        docker-compose -f docker-compose.yml -p motioneye up -d
