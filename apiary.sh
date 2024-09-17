#!/bin/bash

cd /var/lib/beecam/webroot/stream

while true; 
do 
	ffmpeg -i rtsp://admin:honeybee@apiary.home.arpa:554/h265Preview_01_main -fflags flush_packets -max_delay 10 -flags -global_header \
	       -hls_time 5 -hls_list_size 10 -vf crop=1920:1080 -an -c:v h264_nvenc -preset slow -crf 18 -y apiary.m3u8
	echo done; 
	sleep 10; 
done
