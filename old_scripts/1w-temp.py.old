#!/usr/bin/python
import os
import glob
import time
from ISStreamer.Streamer import Streamer

streamer = Streamer(bucket_name="SKYNET-TEMPS",
                bucket_key="8WC35WLXAAAY",
                access_key="XgKetehqZ0ZOkLP91gLsddpj3HYUJK6Q")


os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')
base_dir = '/sys/bus/w1/devices/'
device_folder = glob.glob(base_dir + '28*')[0]
device_file = device_folder + '/w1_slave'
def read_temp_raw():
	f = open(device_file, 'r')
	lines = f.readlines()
	f.close()
	return lines

def read_temp():
	lines = read_temp_raw()
	while lines[0].strip()[-3:] != 'YES':
		time.sleep(0.2)
		lines = read_temp_raw()
	equals_pos = lines[1].find('t=')
	if equals_pos != -1:
		temp_string = lines[1][equals_pos+2:]
		temp_c = float(temp_string) / 1000.0
		temp_f = temp_c * 9.0 / 5.0 + 32.0
		return temp_f

temperature = float(read_temp())

with open("/var/www/html/temp.html", "w") as text_file:
    text_file.write("[{0}]".format(temperature))

streamer.log("MasterPi1Wire-1","%.2f" % temperature)
