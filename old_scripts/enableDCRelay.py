#!/usr/bin/python
import RPi.GPIO as GPIO
import time
import sys

GPIO.setwarnings(False)

pinList = [4,17,27,5,6,13,19,26]

GPIO.setmode(GPIO.BCM)

#str(sys.argv)
#print str(sys.argv)
relayNumber = int(sys.argv[1])
print "Relay %s" % relayNumber
pinNumber = pinList[relayNumber-1]
print "Pin %s" % pinNumber


try:
    GPIO.setup(pinNumber,GPIO.OUT)
    GPIO.output(pinNumber,GPIO.LOW)

except:
    print "shit."
