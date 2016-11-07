#!/usr/bin/python
import os
import glob
import time
from ISStreamer.Streamer import Streamer

def read_temp_raw(which):
        f = open(device_file[which], 'r')
        lines = f.readlines()
        f.close()
        return lines

def read_temp(which):
        lines = read_temp_raw(which)
        while lines[0].strip()[-3:] != 'YES':
                time.sleep(0.2)
                lines = read_temp_raw(which)
        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
                temp_string = lines[1][equals_pos+2:]
                temp_c = float(temp_string) / 1000.0
                temp_f = temp_c * 9.0 / 5.0 + 32.0
                return temp_f


streamer = Streamer(bucket_name="SKYNET-TEMPS",
                bucket_key="8WC35WLXAAAY",
                access_key="XgKetehqZ0ZOkLP91gLsddpj3HYUJK6Q")
pistreamer = Streamer(bucket_name="SKYNET-PI",
                bucket_key="J53VN6NNCYEJ",
                access_key="XgKetehqZ0ZOkLP91gLsddpj3HYUJK6Q")

#Probe 1Wire Serial
os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')
base_dir = '/sys/bus/w1/devices/'

#get all 1wire serial devices in a list
device_folder = glob.glob(base_dir + '28*')
#expect two sensors for the master thermostat node
#sensor 0 == 1 ROOM_AMBIENT_HIGH
#sensor 1 == 2 DUCT_SENSE
#
if len(device_folder) != 2:
        print "ERROR NUM_SENSORS NOT TWO(2)"
	exit()
else:
	device_file = [device_folder[0] + '/w1_slave',device_folder[1] + '/w1_slave']
	
	dummy = read_temp(0)
	dummy = read_temp(1)
	sensor1 = read_temp(0)
	sensor2 = read_temp(1)
	with open("/var/www/html/1wire-1-RM_AMBIENT.html", "w") as text_file:
    		text_file.write("[{0}]".format(sensor1))
        with open("/var/www/html/1wire-2-DUCT.html", "w") as text_file:
                text_file.write("[{0}]".format(sensor2))
	
	streamer.log("ThermostatAmbient","%.2f" % sensor1)
	streamer.log("ThermostatDUCT","%.2f" % sensor2)
	pistreamer.log("ThermostatAmbient","%.2f" % sensor1)
	pistreamer.log("ThermostatDUCT","%.2f" % sensor2)
	print("AMBIENT: %s" % sensor1)
        print("DUCT: %s" % sensor2)
