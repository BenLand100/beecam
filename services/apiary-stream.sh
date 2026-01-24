#!/bin/bash

cd /var/lib/beecam/webroot/stream

# Nvidia nvenc
#exec ffmpeg -rtsp_transport tcp -i rtsp://admin:honeybee@apiary.home.arpa:554/h265Preview_01_main -fflags flush_packets -max_delay 500000 -flags -global_header -hls_time 5 -hls_list_size 10 -vf 'crop=2560:1440:640:250,scale=1920:1080' -an -c:v h264_nvenc -preset slow -crf 18 -y apiary.m3u8

# Intel QuickSync
exec ffmpeg -vaapi_device /dev/dri/renderD128 -hwaccel vaapi -hwaccel_device /dev/dri/renderD128 -hwaccel_output_format vaapi -rtsp_transport tcp -i rtsp://admin:honeybee@apiary.home.arpa:554/h265Preview_01_main -fflags flush_packets -max_delay 500000 -flags -global_header -hls_time 5 -hls_list_size 10 -vf "hwdownload,format=nv12,crop=2560:1440:640:250,scale=1920:1080,hwupload=extra_hw_frames=8,format=vaapi" -tune zerolatency -an -c:v h264_vaapi -preset balanced -qp 20 -y apiary.m3u8

