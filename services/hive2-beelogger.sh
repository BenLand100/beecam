#!/bin/bash

cd /var/lib/beecam

exec ./beelogger.py hive2_log.sqlite http://beelogger2.home.arpa/
