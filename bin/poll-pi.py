#!/usr/bin/python
import time
print "SKYNET-MASTER v1.01"
print "INITIALIZING\n\n"
#Measure init time
t1=time.clock()

#currently implements snmpv1 for compatibility with older HWg devices

from pysnmp.hlapi import *
from ISStreamer.Streamer import Streamer
import re

import subprocess


#Initialize InitialState Streamers
print "Connecting SKYNET-PI to InitialState Logger"
pistreamer = Streamer(bucket_name="SKYNET-PI",
		bucket_key="J53VN6NNCYEJ",
		access_key="XgKetehqZ0ZOkLP91gLsddpj3HYUJK6Q")

#Writing & Logging Block

print "--------------------------------------\n\n"
#compute runtime
t2=time.clock()
print "Run Time: " + "%.2f" % (t2-t1) + ' seconds'

#get pi uptime, print it to console, send it to InitialState
output = subprocess.check_output(['cat','/proc/uptime'])
first = output.split(' ')
uptimeseconds = float(first[0])
print uptimeseconds
hours = uptimeseconds / 3600
print "Thermostat Pi Up " + "%.2f" % (hours)  + " hours"
pistreamer.log("UPTIME-THERMO",str("%.2f" % (hours)))

#get pi gpu/cpu temps, then convert them to degrees F
output = subprocess.check_output(['/opt/skynet/bin/piTemp.sh'])
first = output.split('=')
second = str(first[1]).split()
third = str(second[0]).split('\'')

gpu = (float(third[0]) * 1.8) + 32
cpu = (float(second[1]) / 1000 * 1.8) + 32
print "GPU: " + "%.2f" % gpu
print "CPU: " + "%.2f" % cpu

#upload pi sensor data to initialstate
print "Writing Pi Sensors to InitialState"
pistreamer.log("THERMO Pi GPU", str(gpu))
pistreamer.log("THERMO Pi CPU", str(cpu))
print "Done."
print "--------------------------------------\n\n"

#Final time measure
t3=time.clock()

runtime = "" + '%.2f' % (t3-t1)

#Send run duration to InitialState
pistreamer.log("RUNTIME-THERMO", str(runtime))

#Console output of run duration
print "Final Run Time: " + runtime + ' seconds'
print "Done."


#COMPLETED
