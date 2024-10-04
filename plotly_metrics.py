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


def load_data(count_con, metrics_con, min_date, interval):    
    df_recent = pd.read_sql_query(f"""
        SELECT 
            datetime(floor(unixepoch(timestamp)/{interval})*{interval}, 'unixepoch') as timebin,
            avg(bee_count) as 'Active Bees'
        FROM bee_counter
        WHERE timestamp >= '{min_date}'
        GROUP BY timebin
        ORDER BY timebin
    """, count_con)

    df_metrics = pd.read_sql_query(f"""
        SELECT 
            datetime(floor(unixepoch(coalesce(f.timestamp,s.timestamp))/{interval})*{interval}, 'unixepoch') as timebin,
            10*log10(avg(ambient_lux)/1000) as 'Brightness (dB-klux)', 
            --avg(ambient_lux) as 'Illumination (lux)', 
            2.205*avg(weight) as 'Weight (lbs)', 
            avg(ext_temperature) as 'Temp-Barometer (C)', 
            (avg(ext_pressure)-95)*10 as 'ΔPressure (mbar)',
            avg(temperature_0)*9/5+32 as 'Temp-Under (F)', avg(humidity_0) as 'Humidity-Under (%)',
            avg(temperature_1)*9/5+32 as 'Temp-Brood (F)', avg(humidity_1) as 'Humidity-Brood (%)',
            avg(temperature_2)*9/5+32 as 'Temp-Top (F)', avg(humidity_2) as 'Humidity-Top (%)',
            avg(temperature_3)*9/5+32 as 'Temp-3 (F)', avg(humidity_3) as 'Humidity-3 (%)',
            avg(temperature_4)*9/5+32 as 'Temp-4 (F)', avg(humidity_4) as 'Humidity-4 (%)'
        FROM fast_sensors f
        FULL OUTER JOIN slow_sensors s
        ON f.timestamp = s.timestamp
        WHERE f.timestamp >= '{min_date}' or s.timestamp >= '{min_date}'
        GROUP BY timebin
        ORDER BY timebin
    """, metrics_con)

    return df_metrics.merge(df_recent, on='timebin', how='outer')


def plot_data(df_combined):
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    metrics = list(sorted(set(df_combined.columns) - {'timebin'}))
    for metric in metrics:
        if ~df_combined[metric].isnull().all():
            fig.add_trace(
                go.Scatter(x=df_combined.timebin, y=df_combined[metric], name=metric),
                secondary_y=('lux' in metric or '(C)' in metric or 'Bee' in metric),
            )

    # Set x-axis title
    b = datetime.datetime.now()
    a = b - datetime.timedelta(days=1)
    fig.update_xaxes(title_text="Timestamp", insiderange=[a,b])

    fig.update_layout(
        margin={'t':0,'l':0,'b':0,'r':0}
    )
    
    # Set y-axes titles
    fig.update_yaxes(title_text="°F | lbs | % | Δmbar", secondary_y=False, range=[0,140], fixedrange=True)
    fig.update_yaxes(title_text="Bees | °C | dB-klux", secondary_y=True, range=[0,70], fixedrange=True)
    
    
    return fig

parser = argparse.ArgumentParser(
            prog='beemetrics',
            description='Converts BeeLogger and BeeCounter data into a plotly chart')
parser.add_argument('count_db', help='Sqlite database of BeeCounter counts')
parser.add_argument('metric_db', help='Sqlite database of BeeLogger metrics')
parser.add_argument('html', help='HTML file to generate')
parser.add_argument('-m','--min-date', default='2024-04-10', help='Minimum date to load into plotly')
parser.add_argument('-i','--interval', default=5*60, help='Time step interval in seconds')
parser.add_argument('-s','--sleep', default=15, help='Time to sleep between updates in minutes')

args = parser.parse_args()

metric_con = sqlite3.connect(args.metric_db)
count_con = sqlite3.connect(args.count_db)

while True:

    fig = plot_data(load_data(count_con,metric_con,min_date=args.min_date,interval=args.interval))
    
    html = fig.to_html(full_html=True)

    with open(args.html,'w') as fmetrics:
        fmetrics.write(html)
    
    print(datetime.datetime.now())
    
    time.sleep(args.sleep*60)
