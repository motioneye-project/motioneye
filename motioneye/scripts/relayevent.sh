#!/usr/bin/env sh

if [ -z "$3" ]; then
    echo "Usage: $0 <motioneye.conf> <event> <motion_camera_id> [filename] [camera_dir]"
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
            relay_secret=$(awk '/^# @relay_secret/{print $3}' "$motion_conf")
        fi
    fi
fi

[ "$port" ] || port='8765'

event=$2
motion_camera_id=$3
filename=$4
camera_dir=$5

# send the API a path relative to the camera dir (POSIX prefix strip). Guard
# against an empty camera_dir - e.g. an old motion config calling a newer
# script - so we never strip a bare leading "/". If the prefix does not match,
# the filename is left unchanged and the API still validates it.
if [ -n "$camera_dir" ]; then
    filename=${filename#"$camera_dir"/}
fi

uri="/_relay_event/?event=$event&motion_camera_id=$motion_camera_id"
data="{\"filename\": \"$filename\"}"

# Call relay endpoint with secret header for authentication
curl -sSfm "$timeout" -H 'Content-Type: application/json' -H "X-Relay-Secret: $relay_secret" -X POST "http://127.0.0.1:$port$uri" -d "$data" -o /dev/null
