FROM debian:trixie-slim
LABEL maintainer="Marcus Klein <himself@kleini.org>"

COPY . /tmp/motioneye
COPY docker/entrypoint.sh /entrypoint.sh

RUN << _EOF_
# Install DEB dependencies
case "$(dpkg --print-architecture)" in
	'amd64'|'arm64') PACKAGES='';;
	# Pillow, PycURL
	'ppc64el'|'s390x') PACKAGES='python3-dev gcc libjpeg62-turbo-dev libcurl4-openssl-dev libssl-dev';;
	# Pillow, PycURL, CFFI, cmake (Python module)
	'armel') PACKAGES='python3-dev gcc libjpeg62-turbo-dev libcurl4-openssl-dev libssl-dev libffi-dev make g++';;
	# Pillow, PycURL, CFFI
	*) PACKAGES='python3-dev gcc libjpeg62-turbo-dev libcurl4-openssl-dev libssl-dev libffi-dev';;
esac
apt-get -q update
DEBIAN_FRONTEND='noninteractive' apt-get -qq -o 'Dpkg::Options::=--force-confnew' --no-install-recommends install ca-certificates curl python3 fdisk $PACKAGES

# Install pip
printf '%s\n' '[global]' 'break-system-packages=true' 'no-cache-dir=true' 'root-user-action=ignore' > /etc/pip.conf
curl -sSfO 'https://bootstrap.pypa.io/get-pip.py'
python3 get-pip.py

# Install motionEye
python3 -m pip install -U /tmp/motioneye
motioneye_init --skip-systemd --skip-apt-update

# Setup default config and data dir
mv /etc/motioneye/motioneye.conf /etc/motioneye.conf.sample
# readable by any user given with "docker run --user", it does not contain credentials
chmod 0644 /etc/motioneye.conf.sample
# no config and data dir in the image, so that empty volumes keep the owner they are given (see README.md)
rmdir /etc/motioneye

# Cleanup
python3 -m pip uninstall -y pip
DEBIAN_FRONTEND='noninteractive' apt-get -qq autopurge $PACKAGES
apt-get clean
rm -r /var/lib/apt/lists /var/cache/apt /tmp/motioneye get-pip.py
_EOF_

# R/W needed for motionEye to update configurations
VOLUME /etc/motioneye

# Video & images
VOLUME /var/lib/motioneye

EXPOSE 8765

ENTRYPOINT ["/entrypoint.sh"]
