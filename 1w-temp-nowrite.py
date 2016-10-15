#!/usr/bin/python
import os
import glob
import time
os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')
base_dir = '/sys/bus/w1/devices/'

device1_folder = glob.glob(base_dir + '28*')[0]
device2_folder = glob.glob(base_dir + '28*')[1]

print "folders\n---------"
print device1_folder
print device2_folder

device1_file = device1_folder + '/w1_slave'
device2_file = device2_folder + '/w1_slave'

def read_temp1_raw():
	f = open(device1_file, 'r')
	lines = f.readlines()
	f.close()
	return lines

def read_temp2_raw():
        f = open(device2_file, 'r')
        lines = f.readlines()
        f.close()
        return lines

def read_temp1():
	lines = read_temp1_raw()
	while lines[0].strip()[-3:] != 'YES':
		time.sleep(0.2)
		lines = read_temp1_raw()
	equals_pos = lines[1].find('t=')
	if equals_pos != -1:
		temp_string = lines[1][equals_pos+2:]
		temp_c = float(temp_string) / 1000.0
		temp_f = temp_c * 9.0 / 5.0 + 32.0
		return temp_f

def read_temp2():
        lines = read_temp2_raw()
        while lines[0].strip()[-3:] != 'YES':
                time.sleep(0.2)
                lines = read_temp2_raw()
        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
                temp_string = lines[1][equals_pos+2:]
                temp_c = float(temp_string) / 1000.0
                temp_f = temp_c * 9.0 / 5.0 + 32.0
                return temp_f


dummy = read_temp1()
dummy = read_temp2()
while 1==1:
	os.system('clear')
	print("Sensor 1: %s" % read_temp1())
	print("Sensor 2: %s" % read_temp2())
	time.sleep(2)
