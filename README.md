# motionEye, the motion frontend #

**motionEye **is a web-based user interface for [motion](http://www.lavrsen.dk/foswiki/bin/view/Motion).

## Requirements ##

 * a machine running Linux
 * python 2.6+
 * tornado 3.1+
 * jinja2
 * PIL
 * pycurl
 * motion
 * ffmpeg
 * v4l-utils

On a debian-based system you could run (as root):

    apt-get install motion ffmpeg v4l-utils python-pip
    pip install python-imaging jinja2 pycurl tornado

## Browser Compatibility ##

motionEye works fine with most modern browsers, including IE9+.
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