#!/usr/bin/env python3

import numpy as np
from datetime import datetime, timedelta
import cv2, queue, threading, time, collections
import h5py
from IPython.display import Video, clear_output
import sqlite3
import pandas as pd
import keras
from keras.layers import *
from keras.models import Model
from keras.optimizers import Adam
import itertools
import _thread as thread
import time
import gc
import tracemalloc
import sys
import tensorflow as tf
import argparse

from matplotlib import pyplot as plt

gpus = tf.config.list_physical_devices('GPU')
if gpus:
  try:
    # Currently, memory growth needs to be the same across GPUs
    for gpu in gpus:
      tf.config.experimental.set_memory_growth(gpu, True)
    logical_gpus = tf.config.list_logical_devices('GPU')
    print(len(gpus), "Physical GPUs,", len(logical_gpus), "Logical GPUs")
  except RuntimeError as e:
    # Memory growth must be set before GPUs have been initialized
    print(e)


def construct_model(width, height, base_filter_size):

    def conv_block(i, name, filters, kernel_size=3, activation='relu'):
        c = Conv2D(filters=filters, 
                      kernel_size=kernel_size, 
                      strides=1, 
                      padding='same', 
                      activation=activation, 
                      name=f"{name}_1")(i)
        o = Conv2D(filters=filters, 
                      kernel_size=kernel_size, 
                      strides=2, 
                      padding='same', 
                      activation=activation, 
                      name=f"{name}_2")(c)
        return o
        
    def deconv_block(i, name, filters, activation='relu'):
        up = UpSampling2D(size=2, name=f'up_{name}')(i)
        c =  Conv2D(filters=filters, 
                      kernel_size=3, 
                      strides=1, 
                      padding='same', 
                      activation=activation, 
                      name=f"{name}_1")(up)
        o =  Conv2D(filters=filters, 
                      kernel_size=3, 
                      strides=1, 
                      padding='same', 
                      activation=activation, 
                      name=f"{name}_2")(c)
        return o

    def fix_shape(d, ref_shape):
        if d.shape[1:3] != ref_shape[1:3]:
            cropping = ((0,d.shape[1]-ref_shape[1]),(0,d.shape[2]-ref_shape[2]))
            name,*_ = d.name.split('/')
            d = Cropping2D(cropping=cropping, name=f"crop_{name}")(d)
        return d
    
    image = Input(shape=(height, width, 4), name='input')

    e1 = conv_block(image, 'e1', filters=base_filter_size)
    
    e2 = conv_block(e1, 'e2', filters=2*base_filter_size)
    
    e3 = conv_block(e2, 'e3', filters=4*base_filter_size)
    
    bottleneck = conv_block(e3, 'bottleneck', filters=8*base_filter_size)
    bottleneck = Dropout(0.1)(bottleneck)

    d1 = deconv_block(bottleneck, 'd1', filters=4*base_filter_size)
    d1 = fix_shape(d1, ref_shape=e3.shape)
    d1 = concatenate([d1,e3],axis=3,name='u1')
    
    d2 = deconv_block(d1, 'd2', filters=2*base_filter_size)
    d2 = fix_shape(d2, ref_shape=e2.shape)
    d2 = concatenate([d2,e2],axis=3,name='u2')
    
    d3 = deconv_block(d2, 'd3', filters=base_filter_size)
    d3 = fix_shape(d3, ref_shape=e1.shape)
    d3 = concatenate([d3,e1],axis=3,name='u3')
    
    logits = deconv_block(d3, 'logits', filters=1, activation=None)
    logits = fix_shape(logits, ref_shape=image.shape)

    return Model(inputs=image, outputs=logits)


parser = argparse.ArgumentParser(
            prog='BeeCounter',
            description='Counts bees in a stream that OpenCV can read using AI')
parser.add_argument('count_db', help='Sqlite database for storing the counts')
parser.add_argument('stream', help='URI for a video stream that OpenCV can read')
parser.add_argument('-m','--model',default='model_v5.h5', help='Bee identification model weights')
parser.add_argument('-e','--exit',action='store_true', help='Exit gracefully after some time if there are issues instead of restarting')

args = parser.parse_args()

INPUT_SIZE = (854,480)
LABEL_SIZE = (1366,768)

#tracemalloc.start()

BEGIN = datetime.now()
if args.exit:
    RUNTIME = np.random.random()*15+15

while True:

    model = construct_model(INPUT_SIZE[0], INPUT_SIZE[1], 16)
    model.load_weights(args.model)

    con = sqlite3.connect(args.count_db)
    cur = con.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS bee_counter ( timestamp, bee_count ) ")
    cur.execute("CREATE INDEX IF NOT EXISTS timestamp ON bee_counter ( timestamp )")
    con.commit()

    stream = cv2.VideoCapture(args.stream)

    frames = collections.deque(maxlen=300) # running list of recent history

    skip = 1
    i = 0
    j = 0
    start_ts = datetime.now()
    try:
        #snap_start = tracemalloc.take_snapshot()
        while True:
        
            if args.exit and datetime.now()-timedelta(minutes=RUNTIME) >= BEGIN:
                sys.exit(0)
            
            for _ in range(skip+1):
                res, image = stream.read()
                j = j+1
            i = i+1

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            frames.append(gray)

            if len(frames) > 200 and i%10 == 0:

                print('processing')
                raw = cv2.resize(image, LABEL_SIZE)

                image = cv2.resize(image, INPUT_SIZE)
                image = np.asarray(image, dtype=np.float32)[...,[2,1,0]]
                image = (image - 127) / 128

                fdata = list(itertools.islice(frames, None, len(frames)-100))
                bg = np.mean(np.asarray(fdata), axis=0)
                bg = cv2.resize(bg, INPUT_SIZE)
                bg = np.asarray(bg, dtype=np.float32)
                bg = (bg - 127) / 128

                delta = np.abs(np.mean(image,axis=2) - bg)
                #augmented_input = np.concatenate([image,delta],axis=2)
                #augmented_input = np.stack([image,delta],axis=2)
                augmented_input = np.concatenate([image,delta.reshape(delta.shape+(1,))],axis=2)

                logits = model.predict(np.asarray([augmented_input]))[0]

                thresholded = np.zeros_like(logits,dtype=np.uint8)
                thresholded[logits > 0.0] = 255
                (contours, _) = cv2.findContours(thresholded.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                labels = []
                sizes = []
                maxes = []
                for cnt in contours:
                    x,y,w,h = cv2.boundingRect(cnt)
                    contour = np.zeros_like(logits,np.uint8)
                    cv2.drawContours(contour,[cnt],0,255,-1)
                    mask = contour==255
                    vals = logits[mask]
                    maxidx = np.argmax(vals)
                    maxval = vals[maxidx]
                    y_s,x_s = [dim[maxidx] for dim in np.where(mask)[:2]]
                    print(maxval)
                    if maxval > 0.0:
                        lx,ly = np.asarray([x_s,y_s])/INPUT_SIZE*LABEL_SIZE+0.5
                        lx,ly = int(lx),int(ly)
                        if lx != 0 and ly != 0:
                            labels.append((lx,ly))
                            sizes.append((w,h))
                            maxes.append(maxval)
                cur = con.cursor()
                cur.execute("INSERT INTO bee_counter VALUES (?,?)",(datetime.now(),len(labels)))
                
                if i % 500 == 0:
                    con.commit()
                    print(f'fps: {j/(datetime.now() - start_ts).seconds:0.2f}')
                    
                    gc.collect()
                    keras.backend.clear_session()
                    #snap_now = tracemalloc.take_snapshot()
                    #for detail in snap_now.compare_to(snap_start, 'lineno')[:10]:
                    #    print(detail)
                    
                print(datetime.now(),len(labels),labels)
                
                
                
    except Exception as e:
        print(e)
        time.sleep(10)
