#!/usr/bin/python

import RPi.GPIO as GPIO
#import time

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
#pinList = [4,17,27,5,6,13,19,26]
pinList = [22,17,27,5,6,13,19,26,12,16,20,21]

for i in pinList:
    GPIO.setup(i,GPIO.OUT)

try:
    for x in pinList:
        GPIO.output(x,GPIO.LOW)

except:
    print "shit."

