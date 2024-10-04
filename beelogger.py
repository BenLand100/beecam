#!/usr/bin/env python3

import numpy as np
from datetime import datetime, timedelta
import sqlite3
import pandas as pd
import itertools
import time
import gc
import tracemalloc
import sys
import argparse
import requests
import os

from matplotlib import pyplot as plt


parser = argparse.ArgumentParser(
            prog='beelogger',
            description='Logs data from a BeeLogger Smart Hive')
parser.add_argument('db', help='Sqlite database for storing the data')
parser.add_argument('endpoint', help='URL for the BeeLogger API endpoint')

args = parser.parse_args()

con = sqlite3.connect(args.db)
cur = con.cursor()
cur.execute("""
    CREATE TABLE IF NOT EXISTS fast_sensors (
        timestamp, ambient_lux,
        temperature_0, humidity_0,
        temperature_1, humidity_1,
        temperature_2, humidity_2,
        temperature_3, humidity_3,
        temperature_4, humidity_4
    )
""")
cur.execute("""
    CREATE INDEX IF NOT EXISTS timestamp_fast ON fast_sensors ( timestamp )
""")
cur.execute("""
    CREATE TABLE IF NOT EXISTS slow_sensors (
        timestamp, weight,
        ext_temperature, ext_pressure
    )
""")
cur.execute("""
    CREATE INDEX IF NOT EXISTS timestamp_slow ON slow_sensors ( timestamp )
""")
con.commit()

def read_lux():
    try:
        resp = requests.get(os.path.join(args.endpoint,'lux'), timeout=5).json()
        return resp['ambient_lux']
    except:
        return None
    
print('Lux:',read_lux())

def read_weight():
    try:
        resp = requests.get(os.path.join(args.endpoint,'weight'), timeout=5).json()
        return resp['weight']
    except:
        return None
    
print('Weight:',read_weight())

def read_barometer():
    try:
        resp = requests.get(os.path.join(args.endpoint,'barometer'), timeout=5).json()
        return resp['ext_temperature'], resp['ext_pressure']
    except:
        return None, None
    
print('Barometer:',read_barometer())

def read_temp_humid():
    try:
        resp = requests.get(os.path.join(args.endpoint,'temp_humid'), timeout=5).json()
        result = []
        for i in range(5):
            result.append(resp[f'temperature_{i}'])
            result.append(resp[f'humidity_{i}'])
        return result
    except:
        return [None]*10
    
print('Temp/Humid:',read_temp_humid())

def fast_poll(con):
    cur = con.cursor()
    now = datetime.now()
    lux = read_lux()
    temp_humid = read_temp_humid()[:10]
    print(f'{now}\n\tambient(lux): {lux}\n\ttemperature(C): {temp_humid[::2]}\n\thumidity(%): {temp_humid[1::2]}')
    cur.execute("""
        INSERT INTO fast_sensors(
            timestamp, ambient_lux,
            temperature_0, humidity_0,
            temperature_1, humidity_1,
            temperature_2, humidity_2,
            temperature_3, humidity_3,
            temperature_4, humidity_4
        ) VALUES (
            ?, ?, ?,?, ?,?, ?,?, ?,?, ?,?
        )
        """, (now, lux, *temp_humid)
    )
          
fast_poll(con)

def slow_poll(con):
    cur = con.cursor()
    now = datetime.now()
    weight = read_weight()
    temp,press = read_barometer()
    print(f'{now}\n\tweight(kg): {weight}\n\ttemperature(C): {temp}\n\tpressure(kPa): {press}')
    cur.execute("""
        INSERT INTO slow_sensors(
            timestamp, weight, ext_temperature, ext_pressure
        ) VALUES (
            ?, ?, ?,?
        )
        """, ( now, weight, temp, press)
    )

slow_poll(con)

def commit(con):
    con.commit()

EVENTS = {
    'FAST_POLL': (10, fast_poll),
    'SLOW_POLL': (60, slow_poll),
    'COMMIT': (120, commit),
}

COUNTER = {key:0 for key in EVENTS}

start_ts = datetime.now()
while True:
    total = (datetime.now() - start_ts).total_seconds()
    next_sleep = None
    for key, (period, func) in EVENTS.items():
        if total//period - COUNTER[key] + 1 > 0:
            print(key,f'#{COUNTER[key]+1}','@',total)
            try:
                func(con)
            except Exception as e:
                print(e)
            COUNTER[key] += 1
            break
        remaining = period - total%period
        if next_sleep is None or remaining < next_sleep:
            next_sleep = remaining
    else:        
        print('SLEEP',next_sleep)
        time.sleep(next_sleep)
