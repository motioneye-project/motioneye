#!/usr/bin/env sh

if [ -z "$3" ]; then
    echo "Usage: $0 <motioneye.conf> <event> <motion_camera_id> [filename]"
    exit 1
fi

timeout=5

motioneye_conf=$1
if [ -f "$motioneye_conf" ]; then
    listen=$(grep '^listen' "$motioneye_conf" | cut -d ' ' -f 2)
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

# Connect to the address motionEye listens on, or to loopback if it listens on all addresses
case $listen in
    ''|'0.0.0.0') host='127.0.0.1';;
    '::') host='[::1]';;
    *:*) host="[$listen]";;
    *) host=$listen;;
esac

event=$2
motion_camera_id=$3
filename=$4

uri="/_relay_event/?event=$event&motion_camera_id=$motion_camera_id"
data="{\"filename\": \"$filename\"}"

# Call relay endpoint with secret header for authentication
curl -sSfm "$timeout" -H 'Content-Type: application/json' -H "X-Relay-Secret: $relay_secret" -X POST "http://$host:$port$uri" -d "$data" -o /dev/null
