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

    On **32-bit ARMv6 and ARMv7** systems, thanks to [piwheels](https://piwheels.org/), no development headers are required:
    ```sh
    sudo apt update
    sudo apt --no-install-recommends install ca-certificates curl python3 python3-distutils
    ```

    On **all other architectures** additional development headers are required:
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

    **On recent Debian (Bookworm ant later) and Ubuntu (Lunar and later) versions**, the `libpython3.*-stdlib` package ships a file `/usr/lib/python3.*/EXTERNALLY-MANAGED`, which prevents the installation of Python modules outside of `venv` environments.
    motionEye however has a small number of dependencies with no strict version requirements and hence is very unlikely to break any Python package you might have installed via APT. To bypass this block, add `break-system-packages=true` to the `[global]` section of your `pip.conf`:
    ```sh
    grep -q '\[global\]' /etc/pip.conf 2> /dev/null || printf '%b' '[global]\n' | sudo tee -a /etc/pip.conf > /dev/null
    sudo sed -i '/^\[global\]/a\break-system-packages=true' /etc/pip.conf
    ```

    On **32-bit ARMv6 and ARMv7** systems, additionally configure `pip` to use pre-compiled wheels from [piwheels](https://piwheels.org/):
    ```sh
    grep -q '\[global\]' /etc/pip.conf 2> /dev/null || printf '%b' '[global]\n' | sudo tee -a /etc/pip.conf > /dev/null
    sudo sed -i '/^\[global\]/a\extra-index-url=https://www.piwheels.org/simple/' /etc/pip.conf
    ```

3. Install and setup **motionEye**
    ```sh
    sudo python3 -m pip install --pre motioneye
    sudo motioneye_init
    ```
    _NB: `motioneye_init` currently assumes either an APT- or RPM-based distribution with `systemd` as init system. For a manual setup, config and service files can be found here: <https://github.com/motioneye-project/motioneye/tree/dev/motioneye/extra>_

# Upgrade

```sh
sudo systemctl stop motioneye
sudo python3 -m pip install --upgrade --pre motioneye
sudo systemctl start motioneye
```
