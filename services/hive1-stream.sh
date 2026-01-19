#!/bin/bash

cd /var/lib/beecam/webroot/stream

# Nvidia nvenc
#exec ffmpeg -i rtsp://admin:honeybee@hive1.home.arpa:554/h265Preview_01_main -fflags flush_packets -max_delay 10 -flags -global_header -hls_time 5 -hls_list_size 10 -vf crop=1920:1080 -an -c:v h264_nvenc -preset p6 -crf 18 -y hive1.m3u8

# Intel QuickSync
exec ffmpeg -vaapi_device /dev/dri/renderD128 -hwaccel vaapi -hwaccel_device /dev/dri/renderD128 -hwaccel_output_format vaapi -i rtsp://admin:honeybee@hive1.home.arpa:554/h265Preview_01_main -fflags flush_packets -max_delay 10 -flags -global_header -hls_time 5 -hls_list_size 10 -vf "hwdownload,format=nv12,crop=1920:1080:960:540,hwupload=extra_hw_frames=8,format=vaapi" -tune zerolatency -an -c:v h264_vaapi -preset medium -qp 18 -y hive1.m3u8

