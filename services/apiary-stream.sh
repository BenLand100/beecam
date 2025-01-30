#!/bin/bash

cd /var/lib/beecam/webroot/stream

exec ffmpeg -i rtsp://admin:honeybee@apiary.home.arpa:554/h265Preview_01_main -fflags flush_packets -max_delay 10 -flags -global_header -hls_time 5 -hls_list_size 10 -vf 'crop=2560:1440:640:250,scale=1920:1080' -an -c:v h264_nvenc -preset medium -crf 18 -y apiary.m3u8
