#!/usr/bin/python
import RPi.GPIO as GPIO
import time
 
GPIO.setmode(GPIO.BCM)
 
pinList = [4,17,27,5,6,13,19,26]
 
for i in pinList:
    GPIO.setup(i,GPIO.OUT)

try:
    while True:

#        print "fire"
#	for x in pinList:
#        	GPIO.output(x,GPIO.HIGH)
#        	GPIO.output(x,GPIO.HIGH)
#        time.sleep(2)
 
        print "clear"
        for x in pinList:
                GPIO.output(x,GPIO.LOW)
                GPIO.output(x,GPIO.LOW)
        time.sleep(2)
 
except KeyboardInterrupt:
    print "quit"
    GPIO.cleanup()
