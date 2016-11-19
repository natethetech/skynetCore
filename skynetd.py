#!/usr/bin/python
#Required Syntax: sudo ./skynetd.py start &

#########################################################
#
#  MODULES
#
#########################################################

import sys
import os
import time
import logging
import re
import subprocess
import glob
import RPi.GPIO as GPIO                                  #traditional gpio
from cloudStreamer import *
from datetime import datetime
from datetime import date
from pysnmp.hlapi import *

#from ISStreamer.Streamer import Streamer                 #InitialState Streamer
from daemon import runner

#########################################################
#
#  GLOBALS
#
#########################################################

startTime = time.time()

global cycleCount
cycleCount = 0
cycles = 3

program_weekday = []
program_weekend = []

#SNMP
community = 'public'
port = 161

tempTemps = [0,0,0]
device_file = ["",""]

HVAC_status = [0,0,0,0,0]

HEAT_times = []   #last off   #last on
COOL_times = []

lastUploads = [
        time.time(),     #[0] main_streamer
        time.time(),     #[1] pi_streamer
        time.time()      #[2] double_streamer
        ]

#########################################################
#
#  SETTINGS & DEFAULTS
#
#########################################################

GPIO.setmode(GPIO.BCM)                                   #set pin numbering to broadcom interface number
GPIO.setwarnings(False)
program_file = "/opt/skynet/conf/program.conf"

#########################################################
#
#  SNMP HOSTS
#
#########################################################

tempHosts = [
                ['192.168.1.226','.1.3.6.1.4.1.21796.3.3.3.1.6.3','         Outdoor',-999.9,"__OUTS1__"],
                ['192.168.1.228','.1.3.6.1.4.1.21796.3.3.3.1.6.1','  Master Bedroom',-999.9,"__BEDRM__"],
                ['192.168.1.224','.1.3.6.1.4.1.21796.3.3.3.1.6.1','   Upstairs Hall',-999.9,"__HALL2__"],
                ['192.168.1.224','.1.3.6.1.4.1.21796.3.3.3.1.6.2','           Craft',-999.9,"__CRAFT__"],
                ['192.168.1.225','.1.3.6.1.4.1.21796.3.3.3.1.6.1','       Stairwell',-999.9,"__STAIR__"],
                ['192.168.1.227','.1.3.6.1.4.1.21796.3.3.3.1.6.1','     Living Room',-999.9,"__LVGRM__"],
                ['192.168.1.223','.1.3.6.1.4.1.21796.3.3.3.1.6.1','    UpstairsBath',-999.9,"__BATH2__"],
                ['192.168.1.226','.1.3.6.1.4.1.21796.3.3.3.1.6.2','        Basement',-999.9,"__BSMNT__"],
                ['192.168.1.227','.1.3.6.1.4.1.21796.3.3.3.1.6.2','   Fish Tank 15g',-999.9,"__TNK15__"]
       ]

#NOT YET IMPLEMENTED
humidHosts = [
                ['192.168.1.226','.1.3.6.1.4.1.21796.3.3.3.1.6.1','Outside Humid']
       ]

#########################################################
#
#  GPIO Pin Role Assignment and Constants
#
#########################################################

pinList = [
	5,     #Relay 0: SYSTEM LOCK/ENABLE
	6,     #Relay 1: FAN/Blower Control
	13,    #Relay 2: HEAT Control
	19,    #Relay 3: COOL Control
	21,    #Ghost Relay: AUTOMATIC Control (1) [inverse is MANUAL (0)]
    ]

HVACpin_SYSTEM = 0
HVACpin_FAN = 1
HVACpin_HEAT = 2
HVACpin_COOL = 3
HVACpin_AUTO = 4

oneWirePowerPin = 26
oneWireResetTime = time.time()

#RELAY CONSTANT MAPPINGS
RELAY_ON = GPIO.LOW
RELAY_OFF = GPIO.HIGH

#########################################################
#
#  Rudimentary config for initial logic design
#
#########################################################

setpoint = 72      #rudimentary set temperature for initial logic design
HVAC_which = "BEDRM"
global programPeriodName 
global startHour 
global startMins
global mode
global function
global zones
global set_temp
global hyst_temp
global hyst_time
hyst_temp = 1.0    #degrees over/under before trigger
hyst_time = 600    #seconds until next restart
mode = 2           #0 off 1 fan 2 heat 3 cool

########################################################################################################################
#
#  FUNCTION BLOCKS
#
########################################################################################################################

#########################################################
#
# oneWirePowerInit
#
# initialize (power) the 1-wire power pin
#
#########################################################

def oneWirePowerInit():
	GPIO.setup(oneWirePowerPin, GPIO.OUT)
	GPIO.output(oneWirePowerPin, GPIO.HIGH)

def pollOneWirePower():
	currentOneWirePinStatus = GPIO.input(oneWirePowerPin)
	if currentOneWirePinStatus == GPIO.HIGH:
		logger.info("1-Wire Power Pin: ENABLED/ON")
		double_streamer("1WireReset",0)
	else:
		logger.warn("1-Wire Power Pin: RESET/OFF")
		double_streamer("1WireReset",1)
	
#########################################################
#
# oneWirePowerCycle()
#
# removes and then restores power to the 1wire GPIO pin 
# after 20 seconds
#
#########################################################

def oneWirePowerCycle():
	global oneWireResetTime
	logger.error("oneWirePowerCycle()")
	logger.error(time.time()-oneWireResetTime)
	currentOneWirePinStatus = GPIO.input(oneWirePowerPin)
	if currentOneWirePinStatus == GPIO.HIGH:
		#sensor power is enabled, disable it and mark the time
		oneWireResetTime = time.time()	
		GPIO.output(oneWirePowerPin, GPIO.LOW)
	else:
		#sensor power is already off, check time and re-enable if long enough
		ONE_WIRE_OFF_TIME = 20    #seconds to keep 1-wire sensors off before powering back on
		if time.time() - oneWireResetTime > ONE_WIRE_OFF_TIME:
			GPIO.output(oneWirePowerPin, GPIO.HIGH)
			oneWireResetTime = time.time()

#########################################################
#
# getParams()
#
# Returns an array of the program parameters for right now
# 
# REPLACE WITH SQL relational database
#
#########################################################

def getParams():
	#get the current time as a pair of discrete integers
	rightNow = getTime()
	logger.debug("Current Time: %s" % rightNow)
	nowH = int(rightNow[0])
	nowM = int(rightNow[1])
	
	found = -1
	currentProgram = []
	if isWeekend() == 0:
		for x in range(len(program_weekday)):
			programTime = program_weekday[x][1]		#Yields [hour:minute]
			if nowH >= int(programTime[0]):			#will yield true until proper time slot
				found = x
		currentProgram = program_weekday[found]
	elif isWeekend() == 1:
	        
		for x in range(len(program_weekend)):
                      	programTime = program_weekend[x][1]             #Yields [hour:minute]
		        if nowH >= int(programTime[0]):                 #will yield true until proper time slot  
				found = x  
                currentProgram = program_weekend[found]
        global programPeriodName
        global startHour
        global startMins
        global mode
        global function
        global zones
        global set_temp
        global hyst_temp
        global hyst_time
        programPeriodName=currentProgram[0]
        startHour=int(currentProgram[1][0])
        startMins=int(currentProgram[1][1])
        mode=currentProgram[2]
        function=currentProgram[3]
        zones=currentProgram[4]
        set_temp=float(currentProgram[5])
        hyst_temp=float(currentProgram[6])
        hyst_time=int(currentProgram[7])

#########################################################
#
#  read_program_raw()
#
#  called by load_program() to get actual program file
#
#########################################################

def read_program_raw():
        f = open(program_file, 'r')
        lines = f.readlines()
        f.close()
        return lines

#########################################################
#
#  parse_program(lines)
#
#  called by load_program() to parse program file
#
#########################################################

def parse_program(lines):
	global program_weekday
	global program_weekend
	program_weekday = []
	program_weekend = []
	hyst_time = 0
        if "WEEKDAY" in lines[0]:    			  		#FORMAT TEST: FIRST LINE MUST BE WEEKDAY
            line = 0
            for x in range(8):          		  		#four period setttings for each [weekday|weekend]
                thisblock=line				 		#line counting
                for ticker in range(10):					#eight elements of data plus one blank per block
                    one_var = lines[thisblock+ticker].split('=')
                    if len(one_var) > 1:				#handle expected blank line between sections
                        variableName = one_var[0].strip()		#Strip the line of newlines & unexpected junk
                        value = one_var[1].strip()
                        if 'period' in variableName:			#Begin checking and storing variables
                                period = int(value)
                        if 'name' in variableName:
                                name = value
                        if 'start_time' in variableName:
                                start_time_hhmm = value.split(':')
                                hours = start_time_hhmm[0]
                                minutes = start_time_hhmm[1]
                        if 'function' in variableName:
                                function = value
                        if 'zones' in variableName:
                                zones = value.split(',')
                        if 'set_temp' in variableName:
                                setTemp = float(value)
                        if 'hyst_temp' in variableName:
                                hyst_temp = float(value)
                        if 'hyst_time' in variableName:
                                hyst_time = int(value)
			if 'mode' in variableName:
				mode = value
                    line += 1						#line counting
                if (x < 4):
                        program_weekday.insert(x,[name,[hours,minutes],mode,function,zones,setTemp,hyst_temp,hyst_time])
                if (x >= 4):	
                        program_weekend.insert(x-4,[name,[hours,minutes],mode,function,zones,setTemp,hyst_temp,hyst_time])
	#logger.info("WEEKDAY")
	#for y in range(len(program_weekday)):
	#	logger.info(program_weekday[y])
        #logger.info("WEEKEND")
	#for y in range(len(program_weekend)):
        #        logger.info(program_weekend[y])

#########################################################
#
# load_program()
#
# fetch the Logic Program from the config file & parse
# into arrays for use
# Called at every loop to ensure settings are up to date
#
#########################################################

def load_program():
        lines = read_program_raw()
        parse_program(lines)

#########################################################
#
# getTime()
#
# Returns an array of ["HH","MM"] from current time
#
#########################################################

def getTime():
	return [datetime.now().strftime('%H'),datetime.now().strftime('%M')]

#########################################################
#
# isWeekend()
#
# Returns 0 if weekday
# Returns 1 if weekend
#
#########################################################

def isWeekend():
	dow = date.weekday(datetime.now())
	logger.info("Day of Week: %s" % dow)
	if dow in [5,6]:
		logger.info("WEEKEND")
		return 1
	else:
		logger.info("WEEKDAY")
		return 0

#########################################################
#
# HVAC_service_audit(which)
#
# Check the actual GPIO state for the pin associated with
# the service index provided by 'which'
# Includes logic to detect inconsistencies with stored
# pin states and correct the stored states to match,
# Also includes logic to recognize the automatic virtual
# relay pin and call the appropriate function if that
# pin's state changes.
#
#########################################################

def HVAC_service_audit(which):      
	logger.debug("HVAC_service_audit(%s)" % which)

	pinstat = GPIO.input(pinList[which])
        if pinstat:
        	pinstatus = 0
        else:
                pinstatus = 1
        if (HVAC_status[which] != pinstatus) and (which != HVACpin_AUTO):
                logger.info("*****Pin Change Detected on relay %s" % which)
                logger.info("*****HVAC_status: %s" % HVAC_status[which])
                logger.info("*****Pin Status: %s" % pinstatus)
                HVAC_status[which] = pinstatus
	elif (HVAC_status[which] != pinstatus) and (which == HVACpin_AUTO):
		logger.info("**********AUTOMATIC MODE CHANGE DETECTED***************")
		if pinstat:
			#manual switch on
			logger.warn("MANUAL MANUAL MANUAL MANUAL MANUAL MANUAL MANUAL MANUAL MANUAL")
			HVAC_goManual()
		else:
			logger.warn("AUTO AUTO AUTO AUTO AUTO AUTO AUTO AUTO AUTO AUTO AUTO AUTO AUTO")
			HVAC_goAuto()

#########################################################
#
# HVAC_goAuto()
#
# Change the state of service index 4 and the associated
# GPIO pin to indicate automatic mode is ON
#
#########################################################

def HVAC_goAuto():
	#test conditions, check relays, then change relays (turn off a/c for heat, etc) in a safe way
	logger.info("HVAC_goAuto()")
	HVAC_status[4] = 1	
        GPIO.output(pinList[4],RELAY_ON)

#########################################################
#
# HVAC_goManual()
#
# Change the state of service index 4 and the associated
# GPIO pin to indicate automatic mode is OFF
#
#########################################################

def HVAC_goManual():
	#test conditions, check relays, then change relays...?
	logger.info("HVAC_goManual()")
	HVAC_status[4] = 0
        GPIO.output(pinList[4],RELAY_OFF)

#########################################################
#
# HVAC_audit()
#
# Check stored service states against their pins' 
# actual states, and adjust stored states to match actual
#
#########################################################  

def HVAC_audit():
	logger.debug("HVAC_audit()")
	relayCounter = 0
	for x in pinList:
		HVAC_service_audit(relayCounter)
		relayCounter += 1

#########################################################
#
# upload_status()
#
# Send InitialState the current status of each service
#    0 = off     1 = on
#
# FUTURE ADD: MOVE ALL INITIALSTATE WORK TO THIS FUNC
#
#########################################################  

def upload_status():
        logger.debug("upload_status()")
	outStatus = ["OFF","ON"]
	ups = [0,0,0,0,0]                                #temporary array for modified upload values
	statusCounter = 0
	for x in range(len(HVAC_status)):
		ups[statusCounter] = float(HVAC_status[statusCounter]) + statusCounter + (float(statusCounter) / 10)
		statusCounter += 1
	#Upload the actual states of each service
	double_streamer("HVAC_SYSTEM",HVAC_status[0])
	double_streamer("HVAC_FAN", HVAC_status[1])
	double_streamer("HVAC_HEAT", HVAC_status[2])
	double_streamer("HVAC_COOL", HVAC_status[3])
	double_streamer("HVAC_AUTO", HVAC_status[4])
	#Upload offset states for each service for graphing
        double_streamer("HVAC_SYSTEM_ADD",ups[0])	
        double_streamer("HVAC_FAN_ADD", ups[1])
        double_streamer("HVAC_HEAT_ADD", ups[2])
        double_streamer("HVAC_COOL_ADD", ups[3])
        double_streamer("HVAC_AUTO_ADD", ups[4])
	#Create a sum of all the statuses for graphing
	HVAC_status_sum = 0
	statusCounter = 0
	for x in range(len(HVAC_status)):
		HVAC_status_sum += ups[statusCounter]
		statusCounter += 1
	#Upload it
	double_streamer("HVAC_STATUS_SUM", HVAC_status_sum)
	#Spit out statuses to logger
	logger.info("***HVAC_SYSTEM is %s" % outStatus[HVAC_status[0]]) 
	logger.info("***HVAC_FAN is %s" % outStatus[HVAC_status[1]]) 
	logger.info("***HVAC_HEAT is %s" % outStatus[HVAC_status[2]]) 
	logger.info("***HVAC_COOL is %s" % outStatus[HVAC_status[3]]) 
	logger.info("***HVAC_AUTO is %s" % outStatus[HVAC_status[4]]) 

#########################################################
#
# HVAC_init()
#
# Set up each GPIO pin as output, off (high)
#
#########################################################  

def HVAC_init():
	logger.debug("HVAC_init()")
	relayCounter = 0
	for x in pinList:
		logger.debug("Relay %s" % relayCounter)
		logger.debug("Pin %s" % x)
		#Set pin states to OUTPUT
		GPIO.setup(pinList[relayCounter], GPIO.OUT)
		logger.debug("Mode Set %s" % relayCounter)
		#Turn off the relay by default
		GPIO.output(pinList[relayCounter],RELAY_OFF)
		#Set the stored state of the relay to off
		HVAC_status[relayCounter] = 0
		logger.debug("Relay %s Off" % relayCounter)
		relayCounter = relayCounter + 1

############################################################
#
# HVAC_logic()
#
# The primary logic AI decision structure
#
############################################################

def HVAC_logic(override):
	logger.debug("HVAC_logic()")
	load_program()      		  			#open, read, and parse config file that contains temps and periods
	getParams()

	logger.info("Program Period Name: %s" % programPeriodName)
	logger.info("               Mode: %s" % mode)
	logger.info("              Zones: %s" % zones)
	logger.info("         Start Hour: %s" % startHour)
	logger.info("           Function: %s" % function)
	logger.info("           Set Temp: %s" % set_temp)
	logger.info("    Hysteresis Temp: %s" % hyst_temp)
	logger.info("    Hysteresis Time: %s sec" % hyst_time)
	
	timeNow = getTime()					#get the time for deciding on periodic events
	############################################################
	#
	# LOGIC GROUP: FAN CYCLE 5 mins of every hour
	#
	############################################################

	if datetime.now().strftime('%M') in ["00","01","02","03","04","05"]:
		HVAC_FAN_on()
	elif HVAC_isAuto() == True:
		HVAC_FAN_off()

        ############################################################
        # 
        # LOGIC GROUP: AUTOMATIC MODE
        #
        ############################################################

	if HVAC_isAuto() or override:
		logger.debug("Automatic Mode")

	        ############################################################
        	# 
        	# LOGIC GROUP: AUTOMATIC: HEAT
        	#
        	############################################################
	        
		if 'heat' in mode:                   
			HVAC_COOL_off()				#Because heat is on, make sure cool stays off
			HVAC_service_audit(2)   		#Check the heat service status
        	        #Look for the sensor indicated by HVAC_which for focus 
			#      (replace with programmed settings!)
			hostCounter=0
			found = 0
			for hostItem in range(len(tempHosts)):
				#THIS NEEDS TO BE MODIFIED TO HANDLE FUNCTIONS AND MULTIPLE ROOMS
				if (found == 0) and (zones[0].upper() in tempHosts[hostCounter][4]):
					ambient = tempHosts[hostCounter][3]
					found = hostCounter
				hostCounter += 1
                        ###########################################################################
			# Upload the values used in decision-making
			#
			#   BREAK THIS OUT OF THIS ROUTINE INTO ITS OWN REPEATING FUNCTION
			#
			double_streamer("HVAC_TargetAmbient","%.2f" % ambient)
                        double_streamer("HVAC_which",hostCounter)
                        double_streamer("HVAC_which_str",tempHosts[found][2])
                        double_streamer("HVAC_SetPoint","%.2f" % set_temp)
			logger.info("Ambient: %s" % ambient)
                	logger.info("Set: %s" % set_temp)
                	
                        ###########################################################################
                        # The actual decision-making
                        #
			if ambient > set_temp + hyst_temp:
                		logger.debug(">>>>>HEAT OFF")
				HVAC_HEAT_off()
                	elif ambient < set_temp - hyst_temp:
                        	logger.debug(">>>>>HEAT ON")
				HVAC_HEAT_on()
                	else:
                        	logger.info(">>>>>>COMFORT RANGE")

        ############################################################
        # 
        # LOGIC GROUP: MANUAL MODE
        #
        ############################################################

	else:
		logger.debug("Manual Mode, Doing Nothing Automatically")


############################################################
#
#  HVAC_SYSTEM_[off|on]
#  Primary control relay, used to "lock out" HEAT/COOL/FAN
#
############################################################

def HVAC_SYSTEM_off():
	#turn off relay 0
	logger.debug("HVAC_SYSTEM_off()")
	GPIO.output(pinList[0],RELAY_OFF)
	HVAC_status[0] = 0
	
def HVAC_SYSTEM_on():
	#turn on relay 0
	logger.debug("HVAC_SYSTEM_on()")
	GPIO.output(pinList[0],RELAY_ON)
	HVAC_status[0] = 1

#########################################################
#
#  HVAC_FAN_[off|on]
#  Relay controlling the circ blower
#
#########################################################

def HVAC_FAN_on():
	#turn on relay 1
        logger.debug("HVAC_FAN_on()")
	GPIO.output(pinList[1],RELAY_ON)
	HVAC_status[1] = 1

def HVAC_FAN_off():
	#turn off relay 1
        logger.debug("HVAC_FAN_off()")
	GPIO.output(pinList[1],RELAY_OFF)
	HVAC_status[1] = 0

#########################################################
#
#  HVAC_HEAT_[off|on]
#  Heat control routines
#
#########################################################  

def HVAC_HEAT_on():
	#turn on relay 2
        logger.debug("HVAC_HEAT_on()")
	GPIO.output(pinList[2],RELAY_ON)
	HVAC_status[2] = 1

def HVAC_HEAT_off():
	#turn off relay 2
        logger.debug("HVAC_HEAT_off()")
	GPIO.output(pinList[2],RELAY_OFF)
	HVAC_status[2] = 0

#########################################################
#
#  HVAC_COOL_[off|on]
#  A/C Control Routines
#
#########################################################  

def HVAC_COOL_on():
	#turn on relay 3
        logger.debug("HVAC_COOL_on()")
	GPIO.output(pinList[3],RELAY_ON)
	HVAC_status[3] = 1

def HVAC_COOL_off():
	#turn off relay 3
        logger.debug("HVAC_COOL_off()")
	GPIO.output(pinList[3],RELAY_OFF)
	HVAC_status[3] = 0

#########################################################
#
#  HVAC_AUTO_[off|on]
#
#########################################################  

def HVAC_AUTO_on():
        #turn on relay 4
        logger.debug("HVAC_AUTO_on()")
        GPIO.output(pinList[4],RELAY_ON)
        HVAC_status[4] = 1

def HVAC_AUTO_off():
        #turn off relay 4
        logger.debug("HVAC_AUTO_off()")
        GPIO.output(pinList[4],RELAY_OFF)
        HVAC_status[4] = 0

def HVAC_isAuto():
	HVAC_service_audit(4)      #update manual/auto service
	if HVAC_status[4] == 0:
		return False
	elif HVAC_status[4] == 1:
		return True
	else:
		logger.error("SERVICE AUDIT - AUTO - FAILED")
		return False

#########################################################
#
#  read_temp_raw(which)
#  read_temp(which)
#
#  Serial Functions for 1-Wire Thermal Sensors
#
#########################################################  

def read_temp_raw(which):
	logger.debug("READ_TEMP_RAW: %s" % which)
        logger.debug(device_file[which])
	f = open(device_file[which], 'r')
        lines = f.readlines()
        f.close()
        return lines

def read_temp(which):
        logger.debug("READ_TEMP: %s" % which)
	lines = read_temp_raw(which)
	logger.debug(lines[0])
	logger.debug(lines[1])
        while lines[0].strip()[-3:] != 'YES':
                time.sleep(0.2)
                lines = read_temp_raw(which)
        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
                temp_string = lines[1][equals_pos+2:]
		temp_c = float(temp_string) / 1000.0
                temp_f = temp_c * 9.0 / 5.0 + 32.0
                return temp_f

#########################################################
#
#  poll_1wire_temps
#  
#  primary 1-wire poller
#
#########################################################  

def poll_1wire_temps():
	logger.debug("poll_1wire_temps()")
	#Probe 1Wire Serial
	os.system('modprobe w1-gpio')
	os.system('modprobe w1-therm')
	base_dir = '/sys/bus/w1/devices/'
	#get all 1wire serial devices in a list
	device_folder = glob.glob(base_dir + '28*')
	#expect two sensors for the master thermostat node
	#sensor 0 == 1 ROOM_AMBIENT_HIGH
	#sensor 1 == 2 DUCT_SENSE
	if len(device_folder) != 2:
		logger.error("1WIRE ERROR: MISSING SENSORS! RUNNING RESET ROUTINE!")
		oneWirePowerCycle()
	else:
		logger.debug("Located both sensors OK")
		device_file[0] = device_folder[0] + '/w1_slave'
		device_file[1] = device_folder[1] + '/w1_slave'
		#read one set of records ahead to smooth out the measurements (prevent 185F bug)
		dummy = read_temp(0)
		dummy = read_temp(1)
		sensor1 = read_temp(0)
		sensor2 = read_temp(1)

		tempTemps[0] = sensor1
		tempTemps[1] = sensor2
		if ((sensor1 != 32.0) and (sensor2 != 32.0)):
			#move this to an independent function
			#write for PRTG
			#with open("/var/www/html/1wire-1-RM_AMBIENT.html", "w") as text_file:
    			#	text_file.write("[{0}]".format(sensor1))
        		#with open("/var/www/html/1wire-2-DUCT.html", "w") as text_file:
                	#	text_file.write("[{0}]".format(sensor2))
			#log to initialstate, both buckets
			double_streamer("ThermostatAmbient","%.2f" % sensor1)
			double_streamer("ThermostatDUCT","%.2f" % sensor2)
			#log to the info log
			logger.info("AMBIENT: %s" % sensor1)
        		logger.info("DUCT: %s" % sensor2)
		
#########################################################
#
#  snmp_poller()
#
#  Primary SNMP Poller, handles C to F conversion
#
#########################################################  

def snmp_poller():
	temperature = 0.0
   	hostCount = 0
        for host in range(len(tempHosts)):
                for (errorIndication,errorStatus,errorIndex,varBinds) in getCmd(SnmpEngine(),
                          CommunityData(community, mpModel=0),              #mpModel=0 enables SNMPv1 (-v1)
                          UdpTransportTarget((tempHosts[host][0], 161)),ContextData(),
                          ObjectType(ObjectIdentity(tempHosts[host][1])),   #Single Target OID
                          lookupMib=False):                                 #Do not resolve OID (-On)

                    if errorIndication:
                        logger.error("SNMP ERROR on host %s" % tempHosts[host][2])
                        logger.error(errorIndication)
                        break

                    elif errorStatus:
                        logger.error(errorStatus)
                        logger.error('%s at %s' % (errorStatus.prettyPrint(),
                            errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))
                        break
                    else:
                        #PRIMARY ACTION HERE
                        temperature = (float(varBinds[0][1])/10 * 1.8) + 32  #convert to F from C and store
                        #Formatted console Output of gathered value
                        logger.info(repr(host) + ': ' + tempHosts[host][2] + ': ' + "%.2f" % temperature + 'F')
                        ###PLAN TO REPLACE THIS CALL WITH SQL:
			tempHosts[host][3] = temperature
                        #Send result to initialstate, heavily stripped and formatted for compatibility
			double_streamer(""+str(tempHosts[host][2]).strip()+"", round(float("%.2f" % temperature),4))
                    hostCount += 1

#########################################################
#
# write_runtime()
#
# Send loop time to initialstate
#
#########################################################  

def write_runtime( before, after):
	diff = after-before
	pi_streamer("CoreRuntime",diff)



#########################################################
#
# write_prtg_snmp()
#
# Write strict HTML files for PRTG to parse for sensors
#
#########################################################  

def write_prtg_snmp():
	#write room sensor data to html
        logger.debug("write_prtg_snmp()")
	with open("/var/www/html/temps.html", "w") as text_file:
  		for host in range(len(tempHosts)):
    			text_file.write("[{0}]".format(tempHosts[host][3]))

#########################################################
#
# uptime_poller()
#
# get and post the thermostat's system uptime
#
#########################################################  

def uptime_poller():
        logger.debug("uptime_poller()")
	#get pi uptime, print it to console, send it to InitialState
	output = subprocess.check_output(['cat','/proc/uptime'])
	first = output.split(' ')
	uptimeseconds = float(first[0])
	hours = uptimeseconds / 3600
	logger.info("Master Pi Up " + "%.2f" % (hours)  + " hours")
	pi_streamer("UPTIME",str("%.2f" % (hours)))
	currentTime = time.time()
	processLifetime = (currentTime - startTime) / 3600
	logger.info("Skynet Daemon Process Lifespan (hours): %s" % processLifetime)
	pi_streamer("Daemon-Uptime", str(processLifetime))


#########################################################
#
#  pi_hardware_poller()
#
#  get and post the pi's CPU and GPU tempeatures
#
#########################################################  

def pi_hardware_poller():
	#get pi gpu/cpu temps, then convert them to degrees F
	output = subprocess.check_output(['/opt/skynet/piTemp.sh'])
	#parse
	first = output.split('=')
	second = str(first[1]).split()
	third = str(second[0]).split('\'')
	#assign & convert
	gpu = (float(third[0]) * 1.8) + 32
	cpu = (float(second[1]) / 1000 * 1.8) + 32
	logger.info("GPU: " + "%.2f" % gpu)
	logger.info("CPU: " + "%.2f" % cpu)
	#write for PRTG
	with open("/var/www/html/pitemps.html", "w") as text_file:
    		text_file.write("[{0}]".format(gpu))
    		text_file.write("[{0}]".format(cpu))
	#submit to initialstate
	pi_streamer("Master Pi GPU", str(gpu))
	pi_streamer("Master Pi CPU", str(cpu))

#########################################################
#
# App() Init Constructor
#
# Called only once, at startup
#
#########################################################  

class App():
    
    def __init__(self):
        self.stdin_path = '/dev/null'
        self.stdout_path = '/var/log/skynet/stdout'
        self.stderr_path = '/var/log/skynet/stderr'
        self.pidfile_path =  '/var/run/skynetd.pid'
        self.pidfile_timeout = 3
            
#########################################################
#
#  CORE
#  __init__(self) above runs first on instantiation
#  run(self) runs on run
#
#########################################################  

    def run(self):
	print "runner"
	print "running"
        logger.info("*****************************************************************")
        logger.info("*****************************************************************")
	logger.info("STARTUP INIT")
	logger.info("Initializing HVAC_init()")
	HVAC_init()
    	logger.info("Initializing 1-Wire Interface()")
	oneWirePowerInit()
        logger.info("*****************************************************************")
        logger.info("INIT: CYCLING RELAYS")

        #turn all the relays off first
	HVAC_SYSTEM_off()
        HVAC_FAN_off()
        HVAC_HEAT_off()
        HVAC_COOL_off()
        HVAC_AUTO_off()

	#system first
	HVAC_SYSTEM_on()
	time.sleep(0.3)
	HVAC_SYSTEM_off()      #Leave system relay off so nothing else can trigger

	#turn all the relays on
	HVAC_FAN_on()
	HVAC_HEAT_on()
	HVAC_COOL_on()
	HVAC_AUTO_on()

	time.sleep(0.3)

	#turn all the relays off
	HVAC_FAN_off()
	HVAC_HEAT_off()
	HVAC_COOL_off()
	HVAC_AUTO_off()

	time.sleep(0.3)

	#start up
	HVAC_goAuto()
	HVAC_SYSTEM_on()

	logger.info("Relay Tests OK, System OFF after init")
        logger.info("*****************************************************************")
        logger.info("INIT: STARTING MAIN LOOP")


#########################################################
#
#  CORE LOOP (body of run goes here)
#
#########################################################  
	while True:
	    t_before=time.clock()
	    try:
		#POLLING BLOCK
		pollOneWirePower()
		snmp_poller()           #Poll HWg Devices via SNMP
		#write_prtg_snmp()       #Write SNMP poll data for PRTG
		uptime_poller()		#Poll this pi's uptime
		pi_hardware_poller()    #Poll this pi's CPU/GPU
		poll_1wire_temps()	#Poll this unit's 1-wire sensors		
		HVAC_audit()
		HVAC_logic(False)	    	
		upload_status()
		HVAC_audit()

	    except (SystemExit,KeyboardInterrupt):
            	# Normal exit getting a signal from the parent process
            	pass
            except:
            	# Something unexpected happened? 
            	logging.exception("Exception")
            finally:
            	logging.info("Finishing")
	    t_after=time.clock()
	    write_runtime(t_before,t_after)
	    global cycleCount
	    cycleCount += 1
	    if cycleCount > cycles+1:
		logger.info("Heartbeat")
		cycleCount = 0
#########################################################
#
#  RUN-ONCE INIT to instantiate App(), set up logger, 
#  and fork the daemon
#
#########################################################  
#CALL INIT
app = App()
#START UP LOGGER
logger = logging.getLogger("Skynet.d")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
handler = logging.FileHandler("/var/log/skynet/skynetd.log")
handler.setFormatter(formatter)
logger.addHandler(handler)
#PASS the instance to the runner
daemon_runner = runner.DaemonRunner(app)
#PRESERVE: This ensures that the logger file handle does not get closed during daemonization
daemon_runner.daemon_context.files_preserve=[handler.stream]
#FORK the daemon and close the parent (and thus any link to the terminal, allowing the program to run without dying)
daemon_runner.do_action()
