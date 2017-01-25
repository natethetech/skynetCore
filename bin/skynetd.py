#!/usr/bin/python
#Required Syntax: sudo ./skynetd.py start &

#########################################################
#
#  Python and 3rd Party MODULES
#
#########################################################

import sys
import os
import time
import re
import subprocess
import glob
import RPi.GPIO as GPIO                                  #traditional gpio
import logging
from datetime import datetime
from datetime import date
from pysnmp.hlapi import *
from daemon import runner

#########################################################
#
#  SKYNET MODULES
#
#########################################################

from streamers import main_streamer,pi_streamer,double_streamer

#########################################################
#
#  Record daemon process startup time
#
#########################################################

startTime = time.time()

#########################################################
#
#  EMPTY GLOBALS INIT
#
#########################################################

global programPeriodName
global startHour
global startMins
global mode
global function
global zones
global set_temp
global hyst_temp
global hyst_time
global logger
global formatter
global handler
global HEAT_runtimes

#########################################################
#
#  GLOBALS INIT
#
#########################################################

ambient = 999

startupBurn = False    #has there been a startup burn yet? if not, hyst_temp is overridden. once true, no longer possible ever

program_weekday = []
program_weekend = []

GPIO.setmode(GPIO.BCM)                                   #set pin numbering to broadcom interface number
GPIO.setwarnings(False)
program_file_home = "/opt/skynet/conf/program.home.conf"
program_file_away = "/opt/skynet/conf/program.away.conf"


tempTemps = [0,0,0]
device_file = ["",""]

HVAC_status = [0,0,0,0,0,0]

HEAT_times = [startTime,startTime]   #0 last off   #1 last on
HEAT_runtimes = [0,0]   #0 last off duration    #1 last on duration
COOL_times = []

lastUploads = [
    startTime,     #[0] main_streamer
    startTime,     #[1] pi_streamer
    startTime      #[2] double_streamer
]

#########################################################
#
#  SNMP Globals & Assignments
#
#########################################################

community = 'public'
port = 161

tempHosts = [
    ['192.168.1.226','.1.3.6.1.4.1.21796.3.3.3.1.6.3','         Outdoor',-999.9,"__OUTS1__"],
    ['192.168.1.228','.1.3.6.1.4.1.21796.3.3.3.1.6.1','  Master Bedroom',-999.9,"__BEDRM__"],
    ['192.168.1.229','.1.3.6.1.4.1.21796.3.3.3.1.6.1','Master Bedroom 2',-999.9,"_BEDRMTV_"],
    ['192.168.1.224','.1.3.6.1.4.1.21796.3.3.3.1.6.1','   Upstairs Hall',-999.9,"__HALL2__"],
    ['192.168.1.224','.1.3.6.1.4.1.21796.3.3.3.1.6.2','           Craft',-999.9,"__CRAFT__"],
    ['192.168.1.225','.1.3.6.1.4.1.21796.3.3.3.1.6.2','       Stairwell',-999.9,"__STAIR__"],
    ['192.168.1.227','.1.3.6.1.4.1.21796.3.3.3.1.6.1','     Living Room',-999.9,"__LVGRM__"],
    ['192.168.1.223','.1.3.6.1.4.1.21796.3.3.3.1.6.1','    UpstairsBath',-999.9,"__BATH2__"],
    ['192.168.1.226','.1.3.6.1.4.1.21796.3.3.3.1.6.2','        Basement',-999.9,"__BSMNT__"],
    ['192.168.1.227','.1.3.6.1.4.1.21796.3.3.3.1.6.2','     Front Foyer',-999.9,"__LVRM3__"],
    ['192.168.1.222','.1.3.6.1.4.1.21796.4.1.3.1.5.1','LivingRoomIntake',-999.9,"__LVRM2__"]
]

humidHosts = [
    ['192.168.1.226','.1.3.6.1.4.1.21796.3.3.3.1.6.1','  Outside Humid',-999.9],
    ['192.168.1.225','.1.3.6.1.4.1.21796.3.3.3.1.6.1','Stairwell Humid',-999.9]
]

SNMP_numHosts = len(tempHosts)
SNMP_numHumidHosts = len(humidHosts)

#########################################################
#
#  GPIO Pin Role Assignment and Constants
#
#########################################################

#MOVE
pinList = [
    5,     #Relay 0: SYSTEM LOCK/ENABLE
    6,     #Relay 1: FAN/Blower Control
    13,    #Relay 2: HEAT Control
    19,    #Relay 3: COOL Control
    21,    #Ghost Relay: AUTOMATIC Control (1) [inverse is MANUAL (0)]
    20     #Ghost Relay: HOME (1) AWAY (0)
    ]


#MOVE
HVACpin_SYSTEM = 0
HVACpin_FAN = 1
HVACpin_HEAT = 2
HVACpin_COOL = 3
HVACpin_AUTO = 4
HVACpin_HOME = 5

oneWirePowerPin = 26
oneWireResetTime = startTime  #set the "last reset time" to now, approx program start time

#MOVE
RELAY_ON = GPIO.HIGH
RELAY_OFF = GPIO.LOW

########################################################################################################################
#
#  FUNCTION BLOCKS: LOGGING
#
########################################################################################################################

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
    global ambient
    global startupBurn
    #logger.debug("upload_status()")
    outStatus = ["OFF","ON"]
    ups = [0,0,0,0,0,0]                                #temporary array for modified upload values
    statusCounter = 0
    #Create a sum of all and each of the statuses for graphing separation
    for x in range(len(HVAC_status)):
        ups[statusCounter] = float(HVAC_status[statusCounter]) + statusCounter + (float(statusCounter) / 10)
        statusCounter += 1
    HVAC_status_sum = 0
    statusCounter = 0
    for x in range(len(HVAC_status)):
        HVAC_status_sum += ups[statusCounter]
        statusCounter += 1
    HVAC_status_sum = round(HVAC_status_sum / float(2.0),1)
    timeNow=time.time()
    if HEAT_runtimes[0] > 0:
        heat_off_duration = "%s" % HEAT_runtimes[0]
    else:
        heat_off_duration = "[INIT]"
    if HEAT_runtimes[1] > 0:
        heat_on_duration = "%s" % HEAT_runtimes[1]
    else:
        heat_on_duration = "[INIT]"
    if HEAT_times[0] != startTime:
        heat_off_time = "%s" % time.ctime(HEAT_times[0])
    else:
        heat_off_time = "[INIT]"
    if HEAT_times[1] != startTime:
        heat_on_time = "%s" % time.ctime(HEAT_times[1])
    else:
        heat_on_time = "[INIT]"

    if HVAC_status[2] == 1:
        seconds_since_last_heat = 0
    else:
        seconds_since_last_heat = round(timeNow-HEAT_times[0],1)

    #Send globals to initialstate
    seconds_since_startup = timeNow - startTime
    double_streamer("startupBurn", str(startupBurn))
    double_streamer("secondsSinceStartup","%.0f" % seconds_since_startup)
    double_streamer("HVAC_SYSTEM",HVAC_status[0])
    double_streamer("HVAC_FAN", HVAC_status[1])
    double_streamer("HVAC_HEAT", HVAC_status[2])
    double_streamer("HVAC_COOL", HVAC_status[3])
    double_streamer("HVAC_AUTO", HVAC_status[4])
    if HVAC_status[4] == 0:
        HVAC_AUTO_STR = "MANUAL"
    else:
        HVAC_AUTO_STR = "AUTOMATIC"
    double_streamer("HVAC_AUTO_STR",HVAC_AUTO_STR)
    double_streamer("HVAC_SYSTEM_ADD",ups[0])
    double_streamer("HVAC_FAN_ADD", ups[1])
    double_streamer("HVAC_HEAT_ADD", ups[2])
    double_streamer("HVAC_COOL_ADD", ups[3])
    double_streamer("HVAC_AUTO_ADD", ups[4])
    double_streamer("HVAC_STATUS_SUM", HVAC_status_sum)
    double_streamer("HVAC_program",programPeriodName.upper())
    double_streamer("HVAC_SetPoint","%s" % set_temp)
    double_streamer("HVAC_TriggerPoint", "%.1f" % (float(set_temp) - float(hyst_temp)))
    double_streamer("HVAC_HystTemp","%.1f" % hyst_temp)
    double_streamer("HVAC_HystTime","%s" % int(hyst_time))
    double_streamer("HVAC_heatLastOn",heat_on_time)
    double_streamer("HVAC_heatLastOnSeconds", heat_on_duration)
    double_streamer("HVAC_heatLastOff",heat_off_time)
    double_streamer("HVAC_heatLastOffSeconds", heat_off_duration)
    double_streamer("SecondsSinceLastBurn",seconds_since_last_heat)
    HVAC_service_audit(5)
    logger.info("STATUS: %s" % HVAC_status[5])
    if HVAC_status[5] == 1:
        homeAway = "HOME"
    else:
        homeAway = "AWAY"
    double_streamer("HomeAway",homeAway)
    zonesString = ""
    for zone in zones:
        zonesString += zone + "+"
    zonesString = zonesString[:len(zonesString)-1]
    double_streamer("HVAC_Zones",zonesString.upper())
    double_streamer("HVAC_Function",function.upper())
    double_streamer("HVAC_Mode",mode.upper())
    for host in range(SNMP_numHumidHosts):
        if (humidHosts[host][3] < 110) and (humidHosts[host][3] > -1):
            double_streamer(""+str(humidHosts[host][2]).strip()+"", "%.1f" % humidHosts[host][3])
    for host in range(SNMP_numHosts):
        if (tempHosts[host][3] < 180) and (tempHosts[host][3] > -180):
            double_streamer(""+str(tempHosts[host][2]).strip()+"", "%.1f" % tempHosts[host][3])


    #Spit out statuses to logger
    if ambient < 200:     #make sure not init
        double_streamer("HVAC_TargetAmbient","%.1f" % ambient)
    #logger.debug(loggerLine())

    tempBuffer = ""
    for services in range(len(HVAC_status)):
        if (HVAC_status[services] == 0):
            tempBuffer += "____ "
        else:
            tempBuffer += "XXXX "
    logger.info(" 00   01   02   03   04   05")
    logger.info("SYST FAN  HEAT COOL AUTO HOME")
    logger.info(tempBuffer)
    logger.info(loggerLine())
    #logger.debug(loggerFormat("Heat Last On") + heat_on_time)
    #logger.debug(loggerFormat("Heat Last On Duration") + heat_on_duration)
    #logger.debug(loggerFormat("Heat Last Off") + heat_off_time)
    #logger.debug(loggerFormat("Heat Last Off Duration") + heat_off_duration)
    #time_since_last_heat = "%ssec " % seconds_since_last_heat
    #time_since_last_heat += "(%shr)" % round(seconds_since_last_heat / 3600,1)
    #logger.debug(loggerFormat("Time Since Last Heat") + time_since_last_heat)
    #time_since_startup = "%.1fsec" % seconds_since_startup
    #time_since_startup += " (%.1fhr)" % (seconds_since_startup / 3600.00)
    #logger.debug(loggerFormat("Time Since Startup") + time_since_startup)
    #logger.debug(loggerLine())
    #logger.debug(loggerFormat("Program Period Name") + "%s" % programPeriodName.upper())
    #logger.debug(loggerFormat("Mode") + "%s" % mode.upper())
    #logger.debug(loggerFormat("Zones") + "%s" % zones)
    #logger.debug(loggerFormat("Start Hour") + "%s" % startHour)
    #logger.debug(loggerFormat("Function") + "%s" % function.upper())
    #logger.debug(loggerFormat("Set Temp") + "%s" % set_temp)
    #logger.debug(loggerFormat("Hysteresis Temp") + "%s" % hyst_temp)
    #logger.debug(loggerFormat("Hysteresis Time") + "%s sec" % hyst_time)
    #logger.debug(loggerFormat("Current Ambient") + "%.1f" % ambient)
    #logger.debug(loggerLine())
    #for host in range(SNMP_numHosts):
    #    #logger.debug(loggerFormat(tempHosts[host][2]) + "%.1f" % tempHosts[host][3] + 'F')
    #logger.debug(loggerLine())
    #for host in range(SNMP_numHumidHosts):
    #    #logger.debug(loggerFormat(humidHosts[host][2]) + "%.1f" % humidHosts[host][3] + '%')
    #logger.debug(loggerLine())

# ########################################################
#
# loggerLine()
#
# ########################################################

global loggerLineWidth
loggerLineWidth = 65
loggerLineExpander = ":"

def loggerLine():
    return (loggerLineExpander * ((loggerLineWidth/len(loggerLineExpander))+1))[:loggerLineWidth]

# ########################################################
#
# loggerFormat(string)
#
# Add spaces to the incoming string to ensure the formatting is consistent
#
# ########################################################

global loggerSpaces
loggerSpaces = 30

def loggerFormat(incoming):
    spacersNeeded = loggerSpaces - len(incoming)
    if spacersNeeded < 0:
        logger.error("FORMATTING ERROR! STRING IS TOO LONG! Current width of labels column: %s characters" % loggerSpaces)
    elif spacersNeeded == 0:
        logger.warn("FORMATTING WARNING! STRING IS SAME WIDTH AS COLUMN! Current width of labels column: %s characters" % loggerSpaces)
    else:
        return (incoming.rjust(loggerSpaces) + ": ")

########################################################################################################################
#
#  FUNCTION BLOCKS: GENERAL
#
########################################################################################################################

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

########################################################################################################################
#
#  FUNCTION BLOCKS: HVAC
#
########################################################################################################################

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
    global logger
    global HVAC_status
    #logger.debug("HVAC_service_audit(%s)" % which)

    pinstat = GPIO.input(pinList[which])
    if pinstat:
        pinstatus = 1
    else:
        pinstatus = 0
    if (HVAC_status[which] != pinstatus) and (which != HVACpin_AUTO):
            #logger.debug("*****Pin Change Detected on relay %s" % which)
            #logger.debug("*****HVAC_status: %s" % HVAC_status[which])
            #logger.debug("*****Pin Status: %s" % pinstatus)
            HVAC_status[which] = pinstatus
            if which == 2:                    #if pin status changed, run the appropriate function so timestamps get updated
                if pinstatus == 1:
                    HVAC_HEAT_on()
                elif pinstatus == 0:
                    HVAC_HEAT_off()
    elif (HVAC_status[which] != pinstatus) and (which == HVACpin_AUTO):
        #logger.debug("**********AUTOMATIC MODE CHANGE DETECTED***************")
        if pinstat:
            logger.warn("AUTO AUTO AUTO AUTO AUTO AUTO AUTO AUTO AUTO AUTO AUTO AUTO AUTO")
            HVAC_goAuto()
        else:
            #manual switch on
            logger.warn("MANUAL MANUAL MANUAL MANUAL MANUAL MANUAL MANUAL MANUAL MANUAL")
            HVAC_goManual()
#########################################################
#
# HVAC_goAuto()
#
# Change the state of service index 4 and the associated
# GPIO pin to indicate automatic mode is ON
#
#########################################################

def HVAC_goAuto():
    global logger
    #test conditions, check relays, then change relays (turn off a/c for heat, etc) in a safe way
    #logger.debug("HVAC_goAuto()")
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
    global logger
    #test conditions, check relays, then change relays...?
    #logger.debug("HVAC_goManual()")
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
    global logger
    #logger.debug("HVAC_audit()")
    for relayCounter in range(len(pinList)):
        HVAC_service_audit(relayCounter)

#########################################################
#
# HVAC_init()
#
# Set up each GPIO pin as output, off (high)
#
#########################################################

def HVAC_init():
    global logger
    #logger.debug("HVAC_init()")
    for relayCounter in range(len(pinList)):
        #logger.debug("Relay %s" % relayCounter)
        #logger.debug("Pin %s" % x)
        #Set pin states to OUTPUT
        GPIO.setup(pinList[relayCounter], GPIO.OUT)
        #logger.debug("Mode Set %s" % relayCounter)
        #Turn off the relay by default
        if relayCounter != 5:
            GPIO.output(pinList[relayCounter],RELAY_OFF)
       #Set the stored state of the relay to off
        HVAC_status[relayCounter] = 0
        #logger.debug("Relay %s Off" % relayCounter)
    GPIO.output(pinList[5],RELAY_ON)   #SET HOME BY DEFAULT

############################################################
#
# HVAC_logic()
#
# The primary logic AI decision structure
#
############################################################

def HVAC_logic(override):
    global logger
    #logger.debug("HVAC_logic()")
    load_program()      		  			#open, read, and parse config file that contains temps and periods
    getParams()

    timeNow = getTime()					#get the time for deciding on periodic events

    ############################################################
    #
    # LOGIC GROUP: AUTOMATIC MODE
    #
    ############################################################

    ############################################################
    #
    # LOGIC GROUP: FAN CYCLE 5 mins of every hour
    #
    ############################################################
    timeNow = time.time()
    global programPeriodName
    if ((datetime.now().strftime('%M') in ["00","01","02","03","04"] and (timeNow-startTime) > 120)) and not ("OVERRIDE" in programPeriodName.upper() and datetime.now().strftime('%M') in ["04","05","06","07","08"]):   ###added to smooth out fan behavior while developing
        HVAC_FAN_on()
    elif HVAC_isAuto() == True:
        HVAC_FAN_off()

    if HVAC_isAuto() or override:
        #logger.debug("Automatic Mode")
        HVAC_logic_runAuto()
    ############################################################
    #
    # LOGIC GROUP: MANUAL MODE
    #
    ############################################################

    else:
        #logger.debug("Manual Mode, Doing Nothing Automatically")
        pass

############################################################
#
# getAmbient()
#
# compute a composite 'ambient' value based on two elements:
# function: avg, max, min, val
# zones: array of room name codes (matched to the array of rooms)
#
############################################################

def getAmbient(func,zones):
    global logger
    #return tempHosts[1][3]
    if 'avg' in func:
        holder = 0.0
        for room in zones:
            holder += tempHosts[getZoneID(room)][3]
        return round(holder / len(zones),1)
    elif 'max' in func:
        holder = tempHosts[getZoneID(zones[0])][3]   #set holder to the first element's temperature
        for tempCompare in zones[1:]:
            tester = tempHosts[getZoneID(tempCompare)][3]
            if tester > holder:
                holder = round(tester,1)
        return holder

    elif 'min' in func:
        holder = tempHosts[getZoneID(zones[0])][3]   #set holder to the first element's temperature
        for tempCompare in zones[1:]:
            tester = tempHosts[getZoneID(tempCompare)][3]
            if tester < holder:
                holder = round(tester,1)
        return holder

    elif 'val' in func:
        zoneID = getZoneID(zones[0])
        return round(tempHosts[zoneID][3],1)
    else:
        logger.error("Unhandled System Function. Check the program config for errors")

############################################################
#
# HVAC_logic_runAuto()
#
# LOGIC GROUP: AUTOMATIC, explicitly called by HVAC_logic()
#
############################################################

def HVAC_logic_runAuto():
    global logger
    if 'heat' in mode:
        HVAC_service_audit(3)                   #Check the cool serice status
        if HVAC_status[3] == 1:
            HVAC_COOL_off()                     #Because heat is on, make sure cool stays off
        HVAC_service_audit(2)                   #Check the heat service status

        global ambient
        ambient = getAmbient(function,zones)

        ###########################################################################
        # The actual decision-making
        #
        global HEAT_times
        global HEAT_runtimes
        timeNow = time.time()
        #logger.debug((timeNow - HEAT_times[0]))
        if ((timeNow - HEAT_times[0]) > hyst_time) or ((timeNow - startTime) > 60 and (((timeNow - startTime) < hyst_time) and startupBurn == False)) or (HVAC_status[2] == 1):
            if ambient >= set_temp + hyst_temp:
                #logger.debug(">>>>>HEAT OFF")
                if HVAC_status[2] == 1:
                    HVAC_HEAT_off()
            elif ambient <= set_temp - hyst_temp:
                #logger.debug(">>>>>HEAT ON")
                global startupBurn
                startupBurn = True
                if HVAC_status[2] == 0:
                    HVAC_HEAT_on()
            else:
                pass
                #logger.debug(">>>>>>COMFORT RANGE")

############################################################
#
#  HVAC_SYSTEM_[off|on]
#  Primary control relay, used to "lock out" HEAT/COOL/FAN
#
############################################################

def HVAC_SYSTEM_off():
    #global logger
    #turn off relay 0
    #logger.debug("HVAC_SYSTEM_off()")
    GPIO.output(pinList[0],RELAY_OFF)
    HVAC_status[0] = 0

def HVAC_SYSTEM_on():
    #global logger
    #turn on relay 0
    #logger.debug("HVAC_SYSTEM_on()")
    GPIO.output(pinList[0],RELAY_ON)
    HVAC_status[0] = 1

#########################################################
#
#  HVAC_FAN_[off|on]
#  Relay controlling the circ blower
#
#########################################################

def HVAC_FAN_on():
    #global logger
    #turn on relay 1
    #logger.debug("HVAC_FAN_on()")
    GPIO.output(pinList[1],RELAY_ON)
    HVAC_status[1] = 1

def HVAC_FAN_off():
    #global logger
    #turn off relay 1
    #logger.debug("HVAC_FAN_off()")
    GPIO.output(pinList[1],RELAY_OFF)
    HVAC_status[1] = 0

#########################################################
#
#  HVAC_HEAT_[off|on]
#  Heat control routines
#
#########################################################

def HVAC_HEAT_on():
    #global logger
    global HEAT_times
    global HEAT_runtimes
    timeNow = time.time()
    if timeNow-startTime >= 60:   #guaranteed 60 seconds of "init"
        HEAT_times[1] = timeNow   #1 index is time-since-ON
        HEAT_runtimes[0] = round(timeNow - HEAT_times[0],1)
        #turn on relay 2
        #logger.debug("HVAC_HEAT_on()")
        GPIO.output(pinList[2],RELAY_ON)
        HVAC_status[2] = 1
        write_heat_lastOn()

def HVAC_HEAT_off():
    #global logger
    global HEAT_times
    global HEAT_runtimes
    timeNow = time.time()
    if timeNow-startTime >= 60:   #guaranteed 60 seconds of "init"
        HEAT_times[0] = timeNow  #0 index is time-since-OFF
        HEAT_runtimes[1] = round(timeNow - HEAT_times[1],1)
        #turn off relay 2
        #logger.debug("HVAC_HEAT_off()")
        GPIO.output(pinList[2],RELAY_OFF)
        HVAC_status[2] = 0
        write_heat_lastOff()

#########################################################
#
#  HVAC_COOL_[off|on]
#  A/C Control Routines
#
#########################################################

def HVAC_COOL_on():
    #global logger
    #turn on relay 3
    #logger.debug("HVAC_COOL_on()")
    GPIO.output(pinList[3],RELAY_ON)
    HVAC_status[3] = 1

def HVAC_COOL_off():
    #global logger
    #turn off relay 3
    #logger.debug("HVAC_COOL_off()")
    GPIO.output(pinList[3],RELAY_OFF)
    HVAC_status[3] = 0

#########################################################
#
#  HVAC_AUTO_[off|on]
#
#########################################################

def HVAC_AUTO_on():
    #global logger
    #turn on relay 4
    #logger.debug("HVAC_AUTO_on()")
    GPIO.output(pinList[4],RELAY_ON)
    HVAC_status[4] = 1

def HVAC_AUTO_off():
    #global logger
    #turn off relay 4
    #logger.debug("HVAC_AUTO_off()")
    GPIO.output(pinList[4],RELAY_OFF)
    HVAC_status[4] = 0

def HVAC_isAuto():
    #global logger
    HVAC_service_audit(4)      #update manual/auto service
    if HVAC_status[4] == 0:
        return False
    elif HVAC_status[4] == 1:
        return True
    else:
        logger.error("SERVICE AUDIT - AUTO - FAILED")
        return False

########################################################################################################################
#
#  FUNCTION BLOCKS: HVAC State Last-On-Off Writer
#
########################################################################################################################

#########################################################
#
# write_heat_lastOff(epoch_secs)
#
#########################################################

def write_heat_lastOff():
    global HEAT_times
    global HEAT_runtimes
    #logger.debug("write_heat_lastOff()")
    #logger.debug("HEAT_times[0]: %s" % HEAT_times[0])
    #logger.debug("HEAT_runtimes[1]: %s" % HEAT_runtimes[0])
    try:
        with open("/opt/skynet/states/heat_last_off", "w") as text_file:
            text_file.write(str(HEAT_times[0]) + "\n")
            text_file.write(str(HEAT_runtimes[1]) + "\n")
            text_file.close()
    except:
        logger.error("heat_lastOff writer error!")

#########################################################
#
# write_heat_lastOn(epoch_secs)
#
#########################################################

def write_heat_lastOn():
    global HEAT_times
    global HEAT_runtimes
    #logger.debug("write_heat_lastOn()")
    #logger.debug("HEAT_times[1]: %s" % HEAT_times[1])
    #logger.debug("HEAT_runtimes[0]: %s" % HEAT_runtimes[1])
    try:
        with open("/opt/skynet/states/heat_last_on", "w") as text_file:
            text_file.write(str(HEAT_times[1]) + "\n")
            text_file.write(str(HEAT_runtimes[0]) + "\n")
            text_file.close()
    except:
        logger.error("heat_lastOn writer error!")

#########################################################
#
# read_heat_lastOff()
#
#########################################################

def read_heat_lastOff():
    global HEAT_times
    global HEAT_runtimes
    #logger.debug("read_heat_lastOff()")
    try:
        with open("/opt/skynet/states/heat_last_off", "r") as text_file:
            HEAT_times[0] = float(text_file.readline().strip())
            HEAT_runtimes[1] = float(text_file.readline().strip())
            text_file.close()
    except:
        logger.error("heat_lastOff reader error!")

#########################################################
#
# read_heat_lastOn()
#
#########################################################

def read_heat_lastOn():
    global HEAT_times
    global HEAT_runtimes
    #logger.debug("read_heat_lastOn()")
    try:
        with open("/opt/skynet/states/heat_last_on", "r") as text_file:
            HEAT_times[1] = float(text_file.readline().strip())
            HEAT_runtimes[0] = float(text_file.readline().strip())
            text_file.close()
    except:
        logger.error("heat_lastOn reader error!")


########################################################################################################################
#
#  FUNCTION BLOCKS: PRTG HTML Writer
#
########################################################################################################################

#########################################################
#
# write_prtg_snmp()
#
# Write strict HTML files for PRTG to parse for sensors
#
#########################################################

def write_prtg_snmp():
    #write room sensor data to html
    #logger.debug("write_prtg_snmp()")
    with open("/var/www/html/temps.html", "w") as text_file:
        for host in range(SNMP_numHosts):
            text_file.write("[{0}]".format(tempHosts[host][3]))

########################################################################################################################
#
#  FUNCTION BLOCKS: Pi Hardware Pollers
#
########################################################################################################################

#########################################################
#
# uptime_poller()
#
# get and post the thermostat's system uptime
#
#########################################################

def uptime_poller():
    #logger.debug("uptime_poller()")
    #get pi uptime, print it to console, send it to InitialState
    output = subprocess.check_output(['cat','/proc/uptime'])
    first = output.split(' ')
    uptimeseconds = float(first[0])
    hours = uptimeseconds / 3600
    #logger.debug(loggerFormat("Thermostat Board Uptime") + "%.4f" % (hours)  + " hours")
    pi_streamer("UPTIME",str("%.4f" % (hours)))
    currentTime = time.time()
    processLifetime = (currentTime - startTime) / 3600
    #logger.debug(loggerFormat("Process Lifespan (hours)") + "%.4f" % processLifetime)
    pi_streamer("Daemon-Uptime", "%.4f" % processLifetime)

########################################################################################################################
#
#  FUNCTION BLOCKS: SNMP Pollers
#
########################################################################################################################

############################################################
#
# getZoneID(zoneName)
#
# return the table index of the zone indicated by zoneName
#
############################################################

def getZoneID(zoneName):
    #Look for the sensor indicated by zoneName
    hostCounter = 0
    found = 0
    for hostItem in range(SNMP_numHosts):
            #THIS NEEDS TO BE MODIFIED TO HANDLE FUNCTIONS AND MULTIPLE ROOMS
            if (found == 0) and (zoneName.upper() in tempHosts[hostCounter][4]):
                    #ambient = tempHosts[hostCounter][3]
                    found = hostCounter
            hostCounter += 1
    if found == 0:
        logger.error("Error occurred during getZoneID()")
    else:
        return found

#########################################################
#
#  snmp_poller()
#
#  Primary SNMP Poller, also handles C to F conversion
#
#########################################################

def snmp_poller():
    temperature = 0.0
    hostCount = 0
    for host in range(SNMP_numHosts):
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
                tempHosts[host][3] = round(temperature,1)
        hostCount += 1

#########################################################
#
#  snmp_humid_poller()
#
#  Primary SNMP Poller, also handles C to F conversion
#
#########################################################

def snmp_humid_poller():
    temperature = 0.0
    hostCount = 0
    for host in range(SNMP_numHumidHosts):
        for (errorIndication,errorStatus,errorIndex,varBinds) in getCmd(SnmpEngine(),
            CommunityData(community, mpModel=0),              #mpModel=0 enables SNMPv1 (-v1)
            UdpTransportTarget((humidHosts[host][0], 161)),ContextData(),
            ObjectType(ObjectIdentity(humidHosts[host][1])),   #Single Target OID
            lookupMib=False):                                 #Do not resolve OID (-On)

            if errorIndication:
                logger.error("SNMP ERROR on host %s" % humidHosts[host][2])
                logger.error(errorIndication)
                break

            elif errorStatus:
                logger.error(errorStatus)
                logger.error('%s at %s' % (errorStatus.prettyPrint(),
                    errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))
                break
            else:
                #PRIMARY ACTION HERE
                humidity = (float(varBinds[0][1]) / 10)
                humidHosts[host][3] = round(humidity,1)
        hostCount += 1


#########################################################
#
#  snmp_writer()
#
#  Primary SNMP Writer
#
#########################################################

def snmp_writer():
    pass

#########################################################
#
#  snmp_heater_poller()
#
#  Secondary SNMP Poller
#
#########################################################

def snmp_heater_poller():
    temperature = 0.0
    hostCount = 0
    #logger.debug(loggerLine())
    for host in range(SNMP_numHosts):
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
                tempHosts[host][3] = round(temperature,1)
        hostCount += 1

########################################################################################################################
#
#  FUNCTION BLOCKS: Time Awareness
#
########################################################################################################################

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
    #logger.debug("Day of Week: %s" % dow)
    if dow in [5,6]:
        #logger.debug("WEEKEND")
        return 1
    else:
        #logger.debug("WEEKDAY")
        return 0

########################################################################################################################
#
#  FUNCTION BLOCKS: 1-Wire Pollers
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

#########################################################
#
# pollOneWirePower()
#
# Check status of 1-wire power supply pin and update IS
#
#########################################################

def pollOneWirePower():
    currentOneWirePinStatus = GPIO.input(oneWirePowerPin)
    if currentOneWirePinStatus == GPIO.HIGH:
        #logger.debug(loggerFormat("1-Wire Power Pin") + "ENABLED/ON")
        double_streamer("1WireReset",0)
    else:
        logger.warn(loggerFormat("1-Wire Power Pin") + "RESET/OFF")
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
    timeNow = time.time()
    logger.error("oneWirePowerCycle()")
    logger.error(timeNow-oneWireResetTime)
    currentOneWirePinStatus = GPIO.input(oneWirePowerPin)
    if currentOneWirePinStatus == GPIO.HIGH:
        #sensor power is enabled, disable it and mark the time
        oneWireResetTime = timeNow
        GPIO.output(oneWirePowerPin, GPIO.LOW)
    else:
        #sensor power is already off, check time and re-enable if long enough
        ONE_WIRE_OFF_TIME = 20    #seconds to keep 1-wire sensors off before powering back on
        if time.time() - oneWireResetTime > ONE_WIRE_OFF_TIME:
            GPIO.output(oneWirePowerPin, GPIO.HIGH)
            oneWireResetTime = timeNow

#########################################################
#
#  read_temp_raw(which)
#  read_temp(which)
#
#  Serial Functions for 1-Wire Thermal Sensors
#
#########################################################

def read_temp_raw(which):
    #logger.debug("READ_TEMP_RAW: %s" % which)
    #logger.debug(device_file[which])
    f = open(device_file[which], 'r')
    lines = f.readlines()
    f.close()
    return lines

def read_temp(which):
    #logger.debug("READ_TEMP: %s" % which)
    lines = read_temp_raw(which)
    #logger.debug(lines[0])
    #logger.debug(lines[1])
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = read_temp_raw(which)
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = float(temp_string) / 1000.0
        temp_f = temp_c * 9.0 / 5.0 + 32.0
        return round(temp_f,1)

#########################################################
#
#  poll_1wire_temps
#
#  primary 1-wire poller
#
#########################################################

def poll_1wire_temps():
    #logger.debug("poll_1wire_temps()")
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
        #logger.debug("Located both sensors OK")
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
            #     text_file.write("[{0}]".format(sensor1))
            #with open("/var/www/html/1wire-2-DUCT.html", "w") as text_file:
            #   text_file.write("[{0}]".format(sensor2))
            #log to initialstate, both buckets
            double_streamer("ThermostatAmbient","%.1f" % sensor1)
            double_streamer("ThermostatDUCT","%.1f" % sensor2)
            #log to the info log
            #logger.debug(loggerLine())
            #logger.debug(loggerFormat("AMBIENT") + "%s" % sensor1)
            #logger.debug(loggerFormat("DUCT") + "%s" % sensor2)

########################################################################################################################
#
#  FUNCTION BLOCKS: Environmental Program Management
#
########################################################################################################################

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
    #logger.debug("Current Time: %s" % rightNow)
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
    HVAC_service_audit(5)
    if HVAC_status[5] == 1: #HOME
        progfile = program_file_home
    else:
        progfile = program_file_away
    f = open(progfile, 'r')
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
        for x in range(8):          		  		#four period setttings for each [weekdayweekend]
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
        #logger.debug(loggerLine())
        #logger.debug("STARTUP INIT")
        #logger.debug("")
        #logger.debug("Initializing Heat On/Off Times")
        read_heat_lastOff()
        read_heat_lastOn()
        #logger.debug(loggerLine())
        #logger.debug("Initializing HVAC_init()")
        HVAC_init()
        #logger.debug(loggerLine())
        #logger.debug("Initializing 1-Wire Interface()")
        oneWirePowerInit()
        #logger.debug(loggerLine())
        #logger.debug("INIT: CYCLING RELAYS")
        #turn all the relays off first
        HVAC_SYSTEM_off()
        HVAC_FAN_off()
        HVAC_HEAT_off()
        HVAC_COOL_off()
        HVAC_AUTO_off()

        #start up
        HVAC_goAuto()
        HVAC_SYSTEM_on()  ###DEVELOPMENT LEAVE SYSTEM OFF

        #logger.debug(loggerLine())
        #logger.debug("INIT: STARTING MAIN LOOP")

    	load_program()      		  			#open, read, and parse config file that contains temps and periods
    	getParams()

        #########################################################
        #
        #  CORE LOOP (body of run goes here)
        #
        #########################################################
        while True:
            t_before=time.clock()
            try:
                upload_status()
                #POLLING BLOCK
                pollOneWirePower()
                snmp_poller()           #Poll HWg Devices via SNMP
                upload_status()

                snmp_humid_poller()           #Poll HWg Devices via SNMP
                upload_status()
                #write_prtg_snmp()       #Write SNMP poll data for PRTG
                uptime_poller()		#Poll this pi's uptime
                #REMOVE THIS FUNC pi_hardware_poller()    #Poll this pi's CPU/GPU
                poll_1wire_temps()	#Poll this unit's 1-wire sensors
                HVAC_audit()
                HVAC_logic(False)
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
#logger.debug("STARTED")
daemon_runner.do_action()
