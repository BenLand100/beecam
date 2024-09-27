#!/bin/bash

cd /var/lib/beecam

exec ./plotly_metrics.py hive1_counts.sqlite hive1_log.sqlite webroot/stream/hive1_metrics.html
