#!/usr/bin/env bash

if [[ -z "$1" ]]; then
    echo "Usage: $0 <motion.conf|thread-*.conf>"
    exit 1
fi

file=$1
tmp_file="${file}.tmp"
bak_file="${file}.bak"

# make a backup
echo "backing up ${file}"
cp "${file}" "${bak_file}"

function adjust_directive() {
    # $1 - old directive
    # $2 - new directive

    if ! grep -q "^$1" "${file}"; then
        return
    fi

    echo "adjusting $1 -> $2"
    sed -ri "s/^$1(.*)/$2\1/" "${file}"
}

function remove_directive() {
    # $1 - old directive

    if ! grep -q "^$1 " "${file}"; then
        return
    fi

    echo "removing $1"

    grep -vE "^$1 " "${file}" > "${tmp_file}"
    mv "${tmp_file}" "${file}"
}


# 3.x -> 4.2
adjust_directive "control_authentication" "webcontrol_authentication"
adjust_directive "control_html_output\s+on" "webcontrol_interface 1"
adjust_directive "control_html_output\s+off" "webcontrol_interface 0"
adjust_directive "control_localhost" "webcontrol_localhost"
adjust_directive "control_port" "webcontrol_port"
adjust_directive "gap" "event_gap"
adjust_directive "jpeg_filename" "picture_filename"
adjust_directive "locate\s+on" "locate_motion_mode on\nlocate_motion_style redbox"
adjust_directive "locate\s+off" "locate_motion_mode off\nlocate_motion_style redbox"
adjust_directive "output_all" "emulate_motion"
adjust_directive "output_normal" "picture_output"
adjust_directive "output_motion" "picture_output_motion"
adjust_directive "thread\s+thread-" "camera camera-"
adjust_directive "#thread\s+thread-" "#camera camera-"
adjust_directive "webcam_localhost" "stream_localhost"
adjust_directive "webcam_maxrate" "stream_maxrate"
adjust_directive "webcam_motion" "stream_motion"
adjust_directive "webcam_port" "stream_port"
adjust_directive "webcam_quality" "stream_quality"

# 4.0/4.1 -> 4.2
adjust_directive "# @name" "camera_name"
adjust_directive "extpipe" "movie_extpipe"
adjust_directive "exif" "picture_exif"
adjust_directive "ffmpeg_bps" "movie_bps"
adjust_directive "ffmpeg_duplicate_frames" "movie_duplicate_frames"
adjust_directive "ffmpeg_output_movies" "movie_output"
adjust_directive "ffmpeg_output_debug_movies" "movie_output_motion"
adjust_directive "ffmpeg_variable_bitrate" "movie_quality"
adjust_directive "ffmpeg_video_codec" "movie_codec"
adjust_directive "lightswitch" "lightswitch_percent"
adjust_directive "max_movie_time" "movie_max_time"
adjust_directive "output_pictures" "picture_output"
adjust_directive "output_debug_pictures" "picture_output_motion"
adjust_directive "quality" "picture_quality"
adjust_directive "process_id_file" "pid_file"
adjust_directive "rtsp_uses_tcp" "netcam_use_tcp"
adjust_directive "text_double\s+on" "text_scale 2"
adjust_directive "text_double\s+off" "text_scale 1"
adjust_directive "webcontrol_html_output\s+on" "webcontrol_interface 1"
adjust_directive "webcontrol_html_output\s+off" "webcontrol_interface 0"

# these video controls have been removed and replaced by vid_control_params directive
# user will have to reconfigure them from scratch
remove_directive "brightness"
remove_directive "contrast"
remove_directive "hue"
remove_directive "saturation"


# rename thread file
bn=$(basename "${file}")
dn=$(dirname "${file}")
if [[ ${bn} =~ thread-(.*)\.conf ]]; then
    mv "${file}" "${dn}/camera-${BASH_REMATCH[1]}.conf"
fi
