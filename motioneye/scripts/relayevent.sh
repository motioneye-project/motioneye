#!/usr/bin/env bash

if [ -z "$3" ]; then
    echo "Usage: $0 <motioneye.conf> <event> <motion_camera_id> [filename]"
    exit -1
fi

timeout=5

motioneye_conf=$1
if [ -f "$motioneye_conf" ]; then
    port=$(cat $motioneye_conf | grep -E '^port' | cut -d ' ' -f 2)
    conf_path=$(cat $motioneye_conf | grep -E '^conf_path' | cut -d ' ' -f 2)
    if [ -n "$conf_path" ]; then
        motion_conf="$conf_path/motion.conf"
        if [ -r "$motion_conf" ]; then
            username=$(cat $motion_conf | grep 'admin_username' | cut -d ' ' -f 3)
            password=$(cat $motion_conf | grep 'admin_password' | cut -d ' ' -f 3 | sed -r 's/[^][a-zA-Z0-9/?_.=&{}":, _]/-/g')
        fi
    fi
fi

test -z "$port" && port="8765"
test -z "$username" && username="admin"

event="$2"
motion_camera_id="$3"
filename="$4"

uri="/_relay_event/?_username=$username&event=$event&motion_camera_id=$motion_camera_id"
data="{\"filename\": \"$filename\"}"
# allow for sha1 usage as well as sha1sum
sha1=$(which sha1sum sha1)
signature=$(echo -n "POST:$uri:$data:$password" | $sha1 | cut -d ' ' -f 1)

curl -s -S -m $timeout -H "Content-Type: application/json" -X POST "http://127.0.0.1:$port$uri&_signature=$signature" -d "$data" >/dev/null

