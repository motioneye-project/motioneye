# What is motionEye?

**motionEye** is an online interface for the software [ _motion_ ](https://motion-project.github.io/), a video surveillance program with motion detection.

Check out the [__wiki__](https://github.com/motioneye-project/motioneye/wiki) for more details. Changelog is available on the [__releases page__](https://github.com/motioneye-project/motioneye/releases).

From version 0.43, **motioneye** is multilingual :

| supported languages| | being translated|
| :--- | :--- | :--- |
| English            <a href="https://hosted.weblate.org/engage/motioneye-project/en/"><img src="https://hosted.weblate.org/widgets/motioneye-project/en/svg-badge.svg" align=right /></a> | German ( _Deutsch_ )   <a href="https://hosted.weblate.org/engage/motioneye-project/de/"><img src="https://hosted.weblate.org/widgets/motioneye-project/de/svg-badge.svg" align=right /></a> | Italian ( _Italiano_ ) <a href="https://hosted.weblate.org/engage/motioneye-project/it/"><img src="https://hosted.weblate.org/widgets/motioneye-project/it/svg-badge.svg" align=right /></a> |
| Esperanto          <a href="https://hosted.weblate.org/engage/motioneye-project/eo/"><img src="https://hosted.weblate.org/widgets/motioneye-project/eo/svg-badge.svg" align=right /></a> | Romanian ( _Română_ ) <a href="https://hosted.weblate.org/engage/motioneye-project/ro/"><img src="https://hosted.weblate.org/widgets/motioneye-project/ro/svg-badge.svg" align=right /></a> | Portuguese ( _Português_ ) <a href="https://hosted.weblate.org/engage/motioneye-project/pt/"><img src="https://hosted.weblate.org/widgets/motioneye-project/pt/svg-badge.svg" align=right /></a> |
| French (Français)  <a href="https://hosted.weblate.org/engage/motioneye-project/fr/"><img src="https://hosted.weblate.org/widgets/motioneye-project/fr/svg-badge.svg" align=right /></a> | Slovak ( _Slovenčina_ ) <a href="https://hosted.weblate.org/engage/motioneye-project/sk/"><img src="https://hosted.weblate.org/widgets/motioneye-project/sk/svg-badge.svg" align=right /></a> | Spanish ( _Español_ ) <a href="https://hosted.weblate.org/engage/motioneye-project/es/"><img src="https://hosted.weblate.org/widgets/motioneye-project/es/svg-badge.svg" align=right /></a> |


| Machine translated | | |
| :--- | :--- | :--- |
| Arabic ( _ﺎﻠﻋﺮﺒﻳﺓ_ )    <a href="https://hosted.weblate.org/engage/motioneye-project/ar/"><img src="https://hosted.weblate.org/widgets/motioneye-project/ar/svg-badge.svg" align=right /></a> | Japanese ( _日本語_ )  <a href="https://hosted.weblate.org/engage/motioneye-project/ja/"><img src="https://hosted.weblate.org/widgets/motioneye-project/ja/svg-badge.svg" align=right /></a>  | Russian ( _Русский_ ) <a href="https://hosted.weblate.org/engage/motioneye-project/ru/"><img src="https://hosted.weblate.org/widgets/motioneye-project/ru/svg-badge.svg" align=right /></a> |
| Bengali ( _বাংলা)_ )    <a href="https://hosted.weblate.org/engage/motioneye-project/bn/"><img src="https://hosted.weblate.org/widgets/motioneye-project/bn/svg-badge.svg" align=right /></a> | Malay ( _ﺐﻫﺎﺳ ﻡﻼﻳﻭ_ )      <a href="https://hosted.weblate.org/engage/motioneye-project/ms/"><img src="https://hosted.weblate.org/widgets/motioneye-project/ms/svg-badge.svg" align=right /></a> | Chinese ( _中文_ )          <a href="https://hosted.weblate.org/engage/motioneye-project/zh/"><img src="https://hosted.weblate.org/widgets/motioneye-project/zh/svg-badge.svg" align=right /></a> |
| Hindi ( _हिन्दी _ )      <a href="https://hosted.weblate.org/engage/motioneye-project/hi/"><img src="https://hosted.weblate.org/widgets/motioneye-project/hi/svg-badge.svg" align=right /></a> | Punjabi ( _ਪੰਜਾਬੀ _ )        <a href="https://hosted.weblate.org/engage/motioneye-project/pa/"><img src="https://hosted.weblate.org/widgets/motioneye-project/pa/svg-badge.svg" align=right /></a> |


You can contribute to translations on [__weblate__](https://hosted.weblate.org/projects/motioneye-project)

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
