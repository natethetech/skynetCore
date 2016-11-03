#!/usr/bin/python

import os
import time

try:
	pidfile = open("/var/run/skynetd.pid")
	pid = (pidfile.read()).strip()
	print("Killing PID %s" % pid)
	os.system("sudo kill -9 %s" % pid)
	time.sleep(2)
except:
	print "Process Is Already Dead\n\n\n"
