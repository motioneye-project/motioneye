# What is motionEye?

**motionEye** is an online interface for the software [_motion_](https://motion-project.github.io/), a video surveillance program with motion detection.

Check out the [__wiki__](https://github.com/motioneye-project/motioneye/wiki) for more details. Changelog is available on the [__releases page__](https://github.com/motioneye-project/motioneye/releases).

From version 0.43, **motionEye** is multilingual:

| [![](https://hosted.weblate.org/widgets/motioneye-project/-/287x66-black.png)<br>![](https://hosted.weblate.org/widgets/motioneye-project/-/multi-auto.svg)](https://hosted.weblate.org/engage/motioneye-project/) |
| -: |

You can contribute to translations on [__Weblate__](https://hosted.weblate.org/projects/motioneye-project).

# Installation

These install instructions are constantly tested via CI/CD pipeline on Debian Bullseye and Ubuntu Focal.

1. Install **Python 3.7 or later** and build dependencies

    _Here the commands for APT-based Linux distributions are given._

    On **32-bit ARMv6 and ARMv7** systems:
    ```sh
    sudo apt update
    sudo apt --no-install-recommends install ca-certificates curl python3 python3-distutils
    ```

    On all other architectures additional development headers are required:
    ```sh
    sudo apt update
    sudo apt --no-install-recommends install ca-certificates curl python3 python3-dev libcurl4-openssl-dev gcc libssl-dev
    ```

2. Install the Python package manager `pip`
    ```sh
    curl -sSfO 'https://bootstrap.pypa.io/get-pip.py'
    sudo python3 get-pip.py
    rm get-pip.py
    ```

    On **32-bit ARMv6 and ARMv7** systems, additionally configure `pip` to use pre-compiled wheels from [piwheels](https://piwheels.org/):
    ```sh
    printf '%b' '[global]\nextra-index-url=https://www.piwheels.org/simple/\n' | sudo tee /etc/pip.conf > /dev/null
    ```

3. Install and setup **motionEye**
    ```sh
    sudo python3 -m pip install 'https://github.com/motioneye-project/motioneye/archive/dev.tar.gz'
    sudo motioneye_init
    ```
    _NB: `motioneye_init` currently assumes either an APT- or RPM-based distribution with `systemd` as init system. For a manual setup, config and service files can be found here: <https://github.com/motioneye-project/motioneye/tree/dev/motioneye/extra>_

# Upgrade

```sh
sudo systemctl stop motioneye
sudo python3 -m pip install --upgrade --force-reinstall --no-deps 'https://github.com/motioneye-project/motioneye/archive/dev.tar.gz'
sudo systemctl start motioneye
```
