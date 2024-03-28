#!/usr/bin/env sh

if [ -z "$3" ]; then
    echo "Usage: $0 <motioneye.conf> <event> <motion_camera_id> [filename]"
    exit 1
fi

timeout=5

motioneye_conf=$1
if [ -f "$motioneye_conf" ]; then
    port=$(grep '^port' "$motioneye_conf" | cut -d ' ' -f 2)
    conf_path=$(grep '^conf_path' "$motioneye_conf" | cut -d ' ' -f 2)
    if [ "$conf_path" ]; then
        motion_conf="$conf_path/motion.conf"
        if [ -r "$motion_conf" ]; then
            username=$(grep 'admin_username' "$motion_conf" | cut -d ' ' -f 3)
            password=$(grep 'admin_password' "$motion_conf" | cut -d ' ' -f 3 | sed -r 's/[^][a-zA-Z0-9/?_.=&{}":, _]/-/g')
        fi
    fi
fi

[ "$port" ] || port='8765'
[ "$username" ] || username='admin'

event=$2
motion_camera_id=$3
filename=$4

uri="/_relay_event/?_username=$username&event=$event&motion_camera_id=$motion_camera_id"
data="{\"filename\": \"$filename\"}"
signature=$(printf '%s' "POST:$uri:$data:$password" | sha1sum | cut -d ' ' -f 1)

curl -sSfm "$timeout" -H 'Content-Type: application/json' -X POST "http://127.0.0.1:$port$uri&_signature=$signature" -d "$data" -o /dev/null
