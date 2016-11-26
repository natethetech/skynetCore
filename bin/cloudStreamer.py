#!/usr/bin/python

from ISStreamer.Streamer import Streamer                 #InitialState Streamer

#########################################################
#
#  STREAMERS for InitialState.com
#
#########################################################

streamer = Streamer(bucket_name="SKYNET-TEMPS",bucket_key="8WC35WLXAAAY",access_key="XgKetehqZ0ZOkLP91gLsddpj3HYUJK6Q", buffer_size=30)
phonestreamer = Streamer(bucket_name="SKYNET-MOBILE",bucket_key="3T5JKNUXJUB9",access_key="XgKetehqZ0ZOkLP91gLsddpj3HYUJK6Q", buffer_size=30)
pistreamer = Streamer(bucket_name="SKYNET-PI",bucket_key="J53VN6NNCYEJ",access_key="XgKetehqZ0ZOkLP91gLsddpj3HYUJK6Q", buffer_size=30)

#########################################################
#
# main_streamer(
#
# write a name & value pair to the primary IS streamer
#
#########################################################

def main_streamer(text,value):
	streamer.log(text,value)

#########################################################
#
# pi_streamer(
#
# write a name & value pair to the pi IS streamer
#
#########################################################

def pi_streamer(text,value):
        pistreamer.log(text,value)

#########################################################
#
# double_streamer(
#
# write a name & value pair to all streamers
#
#########################################################

def double_streamer(text,value):
        streamer.log(text,value)
        phonestreamer.log(text,value)
        pi_streamer(text,value)

