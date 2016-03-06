#!/bin/bash

if [ -z "$3" ]; then
    echo "Usage: $0 <motioneye.conf> <event> <thread_id> [filename]"
    exit -1
fi

motioneye_conf=$1
if [ -f "$motioneye_conf" ]; then
    port=$(cat $motioneye_conf | grep -E '^port' | cut -d ' ' -f 2)
    conf_path=$(cat $motioneye_conf | grep -E '^conf_path' | cut -d ' ' -f 2)
    if [ -n "$conf_path" ]; then
        motion_conf="$conf_path/motion.conf"
        if [ -r "$motion_conf" ]; then
            username=$(cat $motion_conf | grep 'admin_username' | cut -d ' ' -f 3)
            password=$(cat $motion_conf | grep 'admin_password' | cut -d ' ' -f 3)
        fi
    fi
fi

test -z "$port" && port="8765"
test -z "$username" && username="admin"

event="$2"
thread_id="$3"
filename="$4"

uri="/_relay_event/?_username=$username&event=$event&thread_id=$thread_id"
data="{\"filename\": \"$filename\"}"
signature=$(echo -n "POST:$uri:$data:$password" | sha1sum | cut -d ' ' -f 1)

curl -H "Content-Type: application/json" -X POST "http://127.0.0.1:$port$uri&_signature=$signature" -d "$data" &>/dev/null


