#!/usr/bin/python
#streamers.py
#InitialState Streamers Module

#includes

from ISStreamer.Streamer import Streamer                 #InitialState Streamer

IS_bucket_size = 30

streamer = Streamer(bucket_name="SKYNET-TEMPS",bucket_key="8WC35WLXAAAY",access_key="XgKetehqZ0ZOkLP91gLsddpj3HYUJK6Q", buffer_size=IS_bucket_size)
phonestreamer = Streamer(bucket_name="SKYNET-MOBILE",bucket_key="3T5JKNUXJUB9",access_key="XgKetehqZ0ZOkLP91gLsddpj3HYUJK6Q", buffer_size=IS_bucket_size)
pistreamer = Streamer(bucket_name="SKYNET-PI",bucket_key="J53VN6NNCYEJ",access_key="XgKetehqZ0ZOkLP91gLsddpj3HYUJK6Q", buffer_size=IS_bucket_size)
dashstreamer = Streamer(bucket_name="NOCMON-DASH",bucket_key="FSFQQEVXT6TB",access_key="XgKetehqZ0ZOkLP91gLsddpj3HYUJK6Q", buffer_size=IS_bucket_size)

def main_streamer(text,value):
    print "main streamer"
    streamer.log(text,value)

def pi_streamer(text,value):
    print "pi streamer"
    pistreamer.log(text,value)

def double_streamer(text,value):
    print "DOUBLE STREAMER"
    streamer.log(text,value)
    phonestreamer.log(text,value)
    pi_streamer(text,value)
    dashstreamer.log(text,value)
