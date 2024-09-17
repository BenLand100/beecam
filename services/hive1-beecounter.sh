#!/bin/bash

cd /var/lib/beecam

while true; do
    /opt/tf_venv/wrap ./beecounter2.py -e hive1_counts.sqlite -m model_v5.h5 /var/lib/beecam/stream/hive1.m3u8;
    echo 'Python process terminated'
    sleep 10;
done
