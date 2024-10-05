#!/usr/bin/env python3

import numpy as np
import pandas as pd
import argparse
import datetime
import sqlite3
import time
import sys
import os

import plotly.graph_objects as go
from plotly.subplots import make_subplots

def process_from(metrics_db, min_date, interval):
    c = metrics_db.cursor()
    with metrics_db:
        c.execute(f'''
            INSERT INTO summary (timestamp, bee_count)
                SELECT 
                    datetime(floor(unixepoch(b.timestamp)/?)*?, 'unixepoch') as timestamp,
                    avg(b.bee_count) as bee_count
                FROM count.bee_counter b
                WHERE b.timestamp >= ?
                GROUP BY timestamp
                ORDER BY timestamp
            ON CONFLICT(timestamp) DO UPDATE SET
                bee_count = excluded.bee_count
        ''', (interval,interval,min_date))
        c.execute(f'''
            INSERT INTO summary (
                    timestamp, ambient_lux,
                    temperature_0, humidity_0,
                    temperature_1, humidity_1,
                    temperature_2, humidity_2,
                    temperature_3, humidity_3,
                    temperature_4, humidity_4
                ) 
                SELECT 
                    datetime(floor(unixepoch(f.timestamp)/?)*?, 'unixepoch') as timestamp,
                    avg(f.ambient_lux) as ambient_lux, 
                    avg(f.temperature_0) as temperature_0, avg(f.humidity_0) as humidity_0,
                    avg(f.temperature_1) as temperature_1, avg(f.humidity_1) as humidity_1,
                    avg(f.temperature_2) as temperature_2, avg(f.humidity_2) as humidity_2,
                    avg(f.temperature_3) as temperature_3, avg(f.humidity_3) as humidity_3,
                    avg(f.temperature_4) as temperature_4, avg(f.humidity_4) as humidity_4
                FROM log.fast_sensors f
                WHERE f.timestamp >= ? 
                GROUP BY timestamp
                ORDER BY timestamp
            ON CONFLICT(timestamp) DO UPDATE SET
                ambient_lux = excluded.ambient_lux,
                temperature_0 = excluded.temperature_0, humidity_0 = excluded.humidity_0,
                temperature_1 = excluded.temperature_1, humidity_1 = excluded.humidity_1,
                temperature_2 = excluded.temperature_2, humidity_2 = excluded.humidity_2,
                temperature_3 = excluded.temperature_3, humidity_3 = excluded.humidity_3,
                temperature_4 = excluded.temperature_4, humidity_4 = excluded.humidity_4
        ''', (interval,interval,min_date))
        c.execute(f'''
            INSERT INTO summary (timestamp, weight, ext_temperature, ext_pressure)
               SELECT
                    datetime(floor(unixepoch(s.timestamp)/?)*?, 'unixepoch') as timestamp,
                    avg(s.weight) as weight, 
                    avg(s.ext_temperature) as ext_temperature, 
                    avg(s.ext_pressure) as ext_pressure
                FROM log.slow_sensors s
                WHERE s.timestamp >= ? 
                GROUP BY timestamp
                ORDER BY timestamp
            ON CONFLICT(timestamp) DO UPDATE SET
                weight = excluded.weight,
                ext_temperature = excluded.ext_temperature,
                ext_pressure = excluded.ext_pressure
        ''', (interval,interval,min_date))
    c.close()
        
def init(metrics_db, count_path, log_path): 
    c = metrics_db.cursor()
    with metrics_db:
        c.execute('''
            CREATE TABLE IF NOT EXISTS summary ( 
                timestamp DATETIME NOT NULL PRIMARY KEY, 
                bee_count, ambient_lux, weight,
                ext_temperature, ext_pressure,
                temperature_0, humidity_0,
                temperature_1, humidity_1,
                temperature_2, humidity_2,
                temperature_3, humidity_3,
                temperature_4, humidity_4
            )
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS timestamp ON summary ( timestamp )')
        c.execute('ATTACH DATABASE ? AS count', (f'file:{count_path}?mode=ro',)) 
        c.execute('ATTACH DATABASE ? AS log', (f'file:{log_path}?mode=ro',)) 
    c.close()
    
def get_data(metrics_db):
    return pd.read_sql_query(f"""
        SELECT 
            timestamp as timebin,
            bee_count as 'Active Bees',
            10*log10(ambient_lux/1000) as 'Brightness (dB-klux)', 
            2.205*weight as 'Weight (lbs)', 
            ext_temperature as 'Temp-Barometer (C)', 
            (ext_pressure-95)*10 as 'ΔPressure (mbar)',
            temperature_0*9/5+32 as 'Temp-Under (F)', humidity_0 as 'Humidity-Under (%)',
            temperature_1*9/5+32 as 'Temp-Brood (F)', humidity_1 as 'Humidity-Brood (%)',
            temperature_2*9/5+32 as 'Temp-Top (F)', humidity_2 as 'Humidity-Top (%)'
        FROM summary
        ORDER BY timebin
    """, metrics_db)

def plot_data(df_combined):
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    metrics = list(sorted(set(df_combined.columns) - {'timebin'}))
    for metric in metrics:
        if ~df_combined[metric].isnull().all():
            fig.add_trace(
                go.Scatter(x=df_combined.timebin, y=df_combined[metric], name=metric),
                secondary_y=('lux' in metric or '(C)' in metric or 'Bee' in metric),
            )

    b = datetime.datetime.now()
    a = b - datetime.timedelta(days=1)
    fig.update_xaxes(title_text="Timestamp", insiderange=[a,b])

    fig.update_layout(
        margin={'t':0,'l':0,'b':0,'r':0}
    )
    
    fig.update_yaxes(title_text="°F | lbs | % | Δmbar", secondary_y=False, range=[0,140], fixedrange=True)
    fig.update_yaxes(title_text="Bees | °C | dB-klux", secondary_y=True, range=[0,70], fixedrange=True)
    
    return fig

parser = argparse.ArgumentParser(
            prog='beemetrics',
            description='Converts BeeLogger and BeeCounter data into a plotly chart')
parser.add_argument('count_db', help='Sqlite database of BeeCounter counts')
parser.add_argument('log_db', help='Sqlite database of BeeLogger metrics')
parser.add_argument('html', help='HTML file to generate')
parser.add_argument('-m','--min-date', default='2024-04-10', help='Minimum date to load into plotly')
parser.add_argument('-i','--interval', default=5*60, help='Time step interval in seconds')
parser.add_argument('-s','--sleep', default=15, help='Time to sleep between updates in minutes')

args = parser.parse_args()

metrics_db = sqlite3.connect(":memory:")

init(metrics_db, args.count_db, args.log_db)

print('Bootstrapping...')
process_from(metrics_db, args.min_date, args.interval)

print('Entering update loop!')
while True:
    fig = plot_data(get_data(metrics_db))
    html = fig.to_html(full_html=True)
    with open(args.html,'w') as fmetrics:
        fmetrics.write(html)

    print('Updated', datetime.datetime.now())

    time.sleep(args.sleep*60)

    print('Upserting...')
    then = datetime.datetime.now() - datetime.timedelta(minutes=args.sleep*10)
    process_from(metrics_db, then, args.interval)
    print('Done!')
