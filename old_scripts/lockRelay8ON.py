#!/usr/bin/python
import RPi.GPIO as GPIO
import time
 
GPIO.setmode(GPIO.BCM)
 
#pinList = [4,17,27,5,6,13,19,26]
pinList = [4,17,27,5,6,13] 
pinListDisabled = [19,26]

for i in pinList:
    GPIO.setup(i,GPIO.OUT)
for i in pinListDisabled:
    GPIO.setup(i,GPIO.OUT)

try:
    for x in pinList:
        GPIO.output(x,GPIO.LOW)

    for x in pinListDisabled:
	GPIO.output(x,GPIO.HIGH)

except:
    print "shit."
