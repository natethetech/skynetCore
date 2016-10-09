#!/usr/bin/python
import RPi.GPIO as GPIO
import time
 
GPIO.setmode(GPIO.BCM)
 
pinList = [17,27]
 
for i in pinList:
    GPIO.setup(i,GPIO.OUT)
try:
    while True:
        print "fire"
        GPIO.output(17,GPIO.HIGH)
        GPIO.output(27,GPIO.HIGH)
        time.sleep(2)
 
        print "clear"
        GPIO.output(17,GPIO.LOW)
        GPIO.output(27,GPIO.LOW)
        time.sleep(2)
 
except KeyboardInterrupt:
    print "quit"
    GPIO.cleanup()
