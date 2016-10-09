#!/usr/bin/python
import subprocess

output = subprocess.check_output(['/opt/skynet/piTemp.sh'])
first = output.split('=')
second = str(first[1]).split()
third = str(second[0]).split('\'')

gpu = str(third[0])
cpu = float(second[1]) / 1000
print gpu
print cpu



output = subprocess.check_output(['cat','/proc/uptime'])
first = output.split(' ')
uptimeseconds = float(first[0])
print uptimeseconds
hours = uptimeseconds / 3600
print "Master Pi Up " + "%.2f" % (hours)  + " hours"
