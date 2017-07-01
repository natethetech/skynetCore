#!/usr/bin/python
import RPi.GPIO as GPIO
import time
 
GPIO.setmode(GPIO.BCM)
 
pinList = [5,6,13,19]
 
for i in pinList:
    GPIO.setup(i,GPIO.OUT)
try:
    while True:
        print "fire"
	for x in pinList:
            GPIO.output(x,GPIO.HIGH)
        time.sleep(2)
 
        print "clear"
	for x in pinList:
            GPIO.output(x,GPIO.LOW)
        time.sleep(2)
 
except KeyboardInterrupt:
    print "quit"
    GPIO.cleanup()
