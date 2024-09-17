#!/bin/bash

cd /var/lib/beecam/webroot/stream

while true; 
do 
	echo "Cleanup time!"
	find . -name '*.ts' -type f -mmin +5 -delete
	sleep 30
done
