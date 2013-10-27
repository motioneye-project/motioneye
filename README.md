# motionEye, the motion frontend #

**motionEye **is a web-based user interface for [motion](http://www.lavrsen.dk/foswiki/bin/view/Motion).

## Requirements ##

 * a machine running Linux
 * python 2.6+
 * tornado
 * jinja2
 * motion
 * ffmpeg
 * v4l2-utils

On a debian-based system you could run:

    apt-get install python-tornado python-jinja2 motion v4l2-utils

## Browser Compatibility ##

motionEye works fine with most modern browsers, including IE8+.
Being designed with responsiveness in mind, it will also work nicely on mobile devices and tablets.

## Installation ##

 1. download the latest version from [bitbucket](https://bitbucket.org/ccrisan/motioneye/downloads) (use the *Tags* tab).
 2. extract the archive to a directory of your choice (e.g. your home directory):
 
        cd /home/user
        tar zxvf ccrisan-motioneye-xyz.tar.gz
        mv ccrisan-motioneye-xyz motioneye
 
 3. create a `settings.py` file using the default template file (the default settings should do for now):

        cd motioneye 
        cp settings_default.py settings.py
 
 4. motionEye can be run directly from the extracted directory; no root privileges are required:
 
        ./motioneye.py
 
 5. point your favourite browser to <http://localhost:8765>

## Raspberry PI ##

If running motionEye on a Raspberry PI with a *CSI camera board*, see `raspicam/readme.txt`.
Also note that only one camera is supported when using this configuration.

