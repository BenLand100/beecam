#!/bin/bash

cd /var/lib/beecam

exec ./plotly_metrics.py hive2_counts.sqlite hive2_log.sqlite webroot/stream/hive2_metrics.html
