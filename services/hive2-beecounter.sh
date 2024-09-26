#!/bin/bash

cd /var/lib/beecam

exec /opt/tf_venv/wrap ./beecounter2.py hive2_counts.sqlite -m model_v5.h5 /var/lib/beecam/webroot/stream/hive2.m3u8;
