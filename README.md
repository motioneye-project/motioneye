[![CodeFactor rating badge](https://www.codefactor.io/repository/github/motioneye-project/motioneye/badge)](https://www.codefactor.io/repository/github/motioneye-project/motioneye)

# What is motionEye?

**motionEye** is an online interface for the software [_motion_](https://motion-project.github.io/), a video surveillance program with motion detection.

Check out the [__wiki__](https://github.com/motioneye-project/motioneye/wiki) for more details. Changelog is available on the [__releases page__](https://github.com/motioneye-project/motioneye/releases).

From version 0.43, **motionEye** is multilingual:

| [![](https://hosted.weblate.org/widgets/motioneye-project/-/287x66-black.png)<br>![](https://hosted.weblate.org/widgets/motioneye-project/-/multi-auto.svg)](https://hosted.weblate.org/engage/motioneye-project/) |
| -: |

You can contribute to translations on [__Weblate__](https://hosted.weblate.org/projects/motioneye-project).

# Installation

_(Docker images are provided on [Docker Hub](https://hub.docker.com/r/motioneyeproject/motioneye). See [docker/README.md](https://github.com/motioneye-project/motioneye/blob/dev/docker/README.md) for further details.)_

1. Install **Python 3.9 or later** and build dependencies

    Here, the commands for APT-based Linux distributions are given:

    ```sh
    sudo apt update
    sudo apt --no-install-recommends install ca-certificates curl python3-venv
    ```

    > On **ARMv6/ARMv7 (32-bit), RISC-V, and other rare CPU architectures**, additional build dependencies may be required to compile the [Pillow](https://pypi.org/project/pillow/), [PycURL](https://pypi.org/project/pycurl/), and [CFFI](https://pypi.org/project/cffi/) modules:
    >
    > ```sh
    > sudo apt --no-install-recommends install python3-dev gcc libjpeg62-turbo-dev libcurl4-openssl-dev libssl-dev libffi-dev
    > ```

2. Create a Python virtual environment (`venv`) for motionEye

    ```sh
    sudo python3 -m venv --upgrade-deps /opt/motioneye
    ```

3. Install and setup **motionEye**

    ```sh
    sudo /opt/motioneye/bin/pip install motioneye
    sudo /opt/motioneye/bin/motioneye_init
    ```

    `motioneye_init` sets up the systemd service with the `meyectl` of the `venv`, hence it does not need to be activated. Another `meyectl` can be given with `--meyectl /path/to/meyectl`.

    If motionEye was installed with `sudo python3 -m pip install motioneye` before, outside of a `venv`, uninstall it with `sudo python3 -m pip uninstall motioneye` first. Your configuration in `/etc/motioneye` is kept, and `motioneye_init` updates the systemd service.

    > `motioneye_init` currently assumes either an APT- or RPM-based distribution with `systemd` as init system. For a manual setup, config and service files can be found here: <https://github.com/motioneye-project/motioneye/tree/dev/motioneye/extra>

4. Access the web interface

    After having successfully followed the installation instructions, the motionEye server should be running on your system and listening on port **8765**. Fire up your favorite web browser and visit the following URL (replacing `[your_ip]` with... well, your system's IP address):

    ```
    http://[your_ip]:8765/
    ```

    Use usernamme _admin_ with empty password when prompted for credentials. A password must be applied for the admin and surveillance (view-only) user account once saving any configuration changes.

# Upgrade

When upgrading motionEye, remember to restart the service. To rule out any mix of old in-memory backend code with new frontend assets, it is recommended to stop it prior to the upgrade, and start it back up afterwards:

```sh
sudo systemctl stop motioneye
sudo /opt/motioneye/bin/pip install --upgrade motioneye
sudo systemctl start motioneye
```

# Pre-releases

We may push beta versions to PyPI to give upcoming releases some testing period. Those can be installed with `pip`'s `--pre` flag:

```sh
sudo systemctl stop motioneye
sudo /opt/motioneye/bin/pip install --upgrade --pre motioneye
sudo systemctl start motioneye
```

If you want to test a recent commit on our development branch:

```sh
sudo systemctl stop motioneye
sudo /opt/motioneye/bin/pip install --upgrade 'https://github.com/motioneye-project/motioneye/archive/dev.tar.gz'
sudo systemctl start motioneye
```
