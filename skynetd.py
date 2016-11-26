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

from datetime import datetime
from datetime import date
from pysnmp.hlapi import *
from daemon import runner

#########################################################
#
#  MODULES
#
#########################################################

from cloudStreamer import *
from sn1wire import *
from snhosts import *
from htmlWriter import *
from HVAC import *
from progMan import *
from snlogger import *
from piPoller import *
from snmpPoller import *
from sntime import *

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

#########################################################
#
#  GLOBALS INIT
#
#########################################################

ambient = "999"

cycleCount = 0
cycles = 3

program_weekday = []
program_weekend = []

GPIO.setmode(GPIO.BCM)                                   #set pin numbering to broadcom interface number
GPIO.setwarnings(False)
program_file = "/opt/skynet/conf/program.conf"

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

SNMP_numHosts = len(hosts.tempHosts)

#NOT YET IMPLEMENTED


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
oneWireResetTime = time.time()   #set the "last reset time" to now, approx program start time

#VERIFY "logical" VALUES?
RELAY_ON = GPIO.LOW
RELAY_OFF = GPIO.HIGH

########################################################################################################################
#
#  FUNCTION BLOCKS
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
