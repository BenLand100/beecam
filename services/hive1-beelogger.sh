#!/bin/bash

cd /var/lib/beecam

exec ./beelogger.py hive1_log.sqlite http://beelogger1.home.arpa/
