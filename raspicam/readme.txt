This folder is only meaningful for Raspberry PI devices used with the CSI camera board.

1) make sure you have installed uv4l and uv4l-raspicam packages:
    http://www.linux-projects.org/modules/sections/index.php?op=viewarticle&artid=14

2) copy `motion' and `v4l2-ctl' scripts to /usr/local/bin;
they serve as wrappers for their corresponding programs and will
make the CSI camera work out of the box with motionEye:
    sudo cp motion /usr/local/bin
    sudo cp v4l2-ctl /usr/local/bin

3) make the scripts executable:
    sudo chmod +x /usr/local/bin/motion
    sudo chmod +x /usr/local/bin/v4l2-ctl

