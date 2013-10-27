## This folder is only meaningful for Raspberry PI devices used with the CSI camera board. ##

1. make sure you have installed `uv4l` and `uv4l-raspicam` packages:
   <http://www.linux-projects.org/modules/sections/index.php?op=viewarticle&artid=14>

2. copy `motion` and `v4l2-ctl` scripts to `/usr/local/bin`;
   they serve as wrappers for their corresponding programs and will
   make the CSI camera work out of the box with motionEye:
   
        sudo cp motion /usr/local/bin
        sudo cp v4l2-ctl /usr/local/bin

3. make the scripts executable:

        sudo chmod +x /usr/local/bin/motion
        sudo chmod +x /usr/local/bin/v4l2-ctl

4. the `uv4l` daemon must be started at boot; add the following line to `/etc/rc.local`,
   *before* the line that starts motionEye:

        test -x /usr/local/bin/motion && /usr/local/bin/motion -h > /dev/null 2>&1

5. if you wish to start motionEye at boot, add this to `/etc/rc.local` (assuming motionEye lives in pi's home directory):

        sudo -u pi /home/pi/motioneye/motioneye.py > /home/pi/motioneye/run/motioneye.log 2>&1 &

        
## CSI camera board troubleshooting ##

* make sure you run the latest version of the Raspberry PI firmware
(you may need a `rpi-update` for the latest `uv4l` version to work)
* make sure you have enabled the camera module in `raspi-config`
* don't overclock your PI too much, using the camera module causes core overheating already
* don't reduce the memory allocated to the GPU too much
