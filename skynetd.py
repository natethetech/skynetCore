#!/usr/bin/python
# To kick off the script, run the following from the python directory:
#   PYTHONPATH=`pwd` python testdaemon.py start

#standard python libs
import logging
import time
#Python SNMP High-Level API
from pysnmp.hlapi import *
#InitialState Streamer
from ISStreamer.Streamer import Streamer
import re
import subprocess
import os
import glob
#import pigpio
import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)    #set pin numbering to broadcom interface number

#third party libs
from daemon import runner

streamer = Streamer(bucket_name="SKYNET-TEMPS",bucket_key="8WC35WLXAAAY",access_key="XgKetehqZ0ZOkLP91gLsddpj3HYUJK6Q")
pistreamer = Streamer(bucket_name="SKYNET-PI",bucket_key="J53VN6NNCYEJ",access_key="XgKetehqZ0ZOkLP91gLsddpj3HYUJK6Q")

#########################################################
#
#  GLOBALS
#
#########################################################

#SNMP
community = 'public'
port = 161

#GLBOALS
tempTemps = [0,0,0]

#List hosts to poll for Celsius temperatures
tempHosts = [
                ['192.168.1.226','.1.3.6.1.4.1.21796.3.3.3.1.6.3','         Outdoor',-999.9,"OUTSIDE"],
                ['192.168.1.228','.1.3.6.1.4.1.21796.3.3.3.1.6.1','  Master Bedroom',-999.9,"MASTERBED"],
                ['192.168.1.224','.1.3.6.1.4.1.21796.3.3.3.1.6.1','   Upstairs Hall',-999.9,"UPHALL"],
                ['192.168.1.224','.1.3.6.1.4.1.21796.3.3.3.1.6.2','           Craft',-999.9,"CRAFT"],
                ['192.168.1.225','.1.3.6.1.4.1.21796.3.3.3.1.6.1','       Stairwell',-999.9,"STAIRS"],
                ['192.168.1.227','.1.3.6.1.4.1.21796.3.3.3.1.6.1','     Living Room',-999.9,"LIVINGRM"],
                ['192.168.1.223','.1.3.6.1.4.1.21796.3.3.3.1.6.1','         Kitchen',-999.9,"KITCHEN"],
                ['192.168.1.226','.1.3.6.1.4.1.21796.3.3.3.1.6.2','        Basement',-999.9,"BASEMENT"],
                ['192.168.1.227','.1.3.6.1.4.1.21796.3.3.3.1.6.2','   Fish Tank 15g',-999.9,"FISH15"]
       ]

#List hosts to poll for Humidity (%RH) 
#NOT YET IMPLEMENTED
humidHosts = [
                ['192.168.1.226','.1.3.6.1.4.1.21796.3.3.3.1.6.1','Outside Humid']
       ]

device_file = ["",""]

###########
# GPIO Manipulation for Relay Control
# Master Thermostat Pinout: 5,6,13,19
pinList = [
	5,     #Relay 0: SYSTEM LOCK/ENABLE
	6,     #Relay 1: FAN/Blower Control
	13,    #Relay 2: HEAT Control
	19     #Relay 3: COOL Control
    ]
#thisPi = pigpio.pi()
#if not thisPi.connected:
#	#handle this error somehow
#	print "BAD CONNECT STATE"
#else:
#	print "Proceeding"

RELAY_ON = GPIO.LOW
RELAY_OFF = GPIO.HIGH

GPIO.setwarnings(False)

HVAC_status = [0,0,0,0]

HEAT_times = [0,0]   #last off   #last on
COOL_times = [0,0]

#rudimentary config for initial logic design
mode = 2 #0 off 1 fan 2 heat 3 cool
setpoint = 73      #rudimentary set temperature for initial logic design
hyst_temp = 1.0    #degrees over/under before trigger
hyst_time = 600    #seconds until next restart

#########################################################
#
#  Send InitialState the current status of each component
#  0 = off     1 = on
#
#########################################################  

def upload_status():
	#streamer.log("HVAC_test","ON")
	streamer.log("HVAC_SYSTEM",HVAC_status[0])
	streamer.log("HVAC_FAN", HVAC_status[1])
	streamer.log("HVAC_HEAT", HVAC_status[2])
	streamer.log("HVAC_COOL", HVAC_status[3])
	logger.debug(HVAC_status)
	streamer.log("HVAC_test", "OFF")

#########################################################
#
#  HVAC_init
#  Set up each GPIO pin as output, off (high)
#
#########################################################  

def HVAC_init():
	logger.debug("HVAC_init() called")

	#if not thisPi.connected:
	#	logger.error("BAD CONNECT STATE")
	#else:
	#	logger.debug("Connect State Verified")

	relayCounter = 0
	for x in pinList:
		logger.debug("Relay %s" % relayCounter)
		logger.debug("Pin %s" % x)
		GPIO.setup(pinList[relayCounter], GPIO.OUT)  	      #pin mode to output
		logger.debug("Mode Set %s" % relayCounter)
		GPIO.output(pinList[relayCounter],RELAY_OFF)          #turn off the relay
		HVAC_status[relayCounter] = 0
		logger.debug("Relay %s Off" % relayCounter)
		relayCounter = relayCounter + 1

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
	logger.debug("file opened")
        lines = f.readlines()
	logger.debug("lines read")
        f.close()
	logger.debug(lines)
        return lines

def read_temp(which):
        logger.debug("READ_TEMP: %s" % which)
	logger.debug(device_file[which])
	lines = read_temp_raw(which)
	logger.debug(lines)
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
	logger.info("Polling 1wire bus")
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
		logger.error("1WIRE ERROR: MISSING SENSORS! LOOPING W/O DOING ANYTHING HERE!")
	else:
		logger.info("Located both sensors OK")
		device_file[0] = device_folder[0] + '/w1_slave'
		device_file[1] = device_folder[1] + '/w1_slave'
		#read one set of records ahead to smooth out the measurements (prevent 185F bug)
		logger.debug(device_file)
		dummy = read_temp(0)
		dummy = read_temp(1)
		sensor1 = read_temp(0)
		sensor2 = read_temp(1)
		tempTemps[0] = sensor1
		tempTemps[1] = sensor2
		#write for PRTG
		with open("/var/www/html/1wire-1-RM_AMBIENT.html", "w") as text_file:
    			text_file.write("[{0}]".format(sensor1))
        	with open("/var/www/html/1wire-2-DUCT.html", "w") as text_file:
                	text_file.write("[{0}]".format(sensor2))
		#log to initialstate, both buckets
		streamer.log("ThermostatAmbient","%.2f" % sensor1)
		streamer.log("ThermostatDUCT","%.2f" % sensor2)
		pistreamer.log("ThermostatAmbient","%.2f" % sensor1)
		pistreamer.log("ThermostatDUCT","%.2f" % sensor2)
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
        logger.info("SNMP Temperature Sensor Poller")
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
                        tempHosts[host][3] = temperature
                        #Send result to initialstate, heavily stripped and formatted for compatibility
                        streamer.log(""+str(tempHosts[host][2]).strip()+"", round(float("%.2f" % temperature),4))
			
#########################################################
#
#  Write strict HTML files for PRTG to parse for sensors
#
#########################################################  

def write_prtg_snmp():
	#compute runtime
	#t2=time.clock()
	#print "Run Time: " + "%.2f" % (t2-t1) + ' seconds'
	#write room sensor data to html
	logger.info("Writing Room Sensors HTML for PRTG")
	with open("/var/www/html/temps.html", "w") as text_file:
  		for host in range(len(tempHosts)):
    			text_file.write("[{0}]".format(tempHosts[host][3]))

#########################################################
#
#  uptime_poller()
#  get and post the thermostat's system uptime
#
#########################################################  

def uptime_poller():
	#get pi uptime, print it to console, send it to InitialState
	output = subprocess.check_output(['cat','/proc/uptime'])
	first = output.split(' ')
	uptimeseconds = float(first[0])
	hours = uptimeseconds / 3600
	logger.info("Master Pi Up " + "%.2f" % (hours)  + " hours")
	pistreamer.log("UPTIME",str("%.2f" % (hours)))

#########################################################
#
#  pi_hardware_poller()
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
	pistreamer.log("Master Pi GPU", str(gpu))
	pistreamer.log("Master Pi CPU", str(cpu))

#########################################################
#
#  Constructors for primary superclass
#
#########################################################  

class App():
    
    def __init__(self):
        self.stdin_path = '/dev/null'
        self.stdout_path = '/dev/tty'
        self.stderr_path = '/dev/tty'
        self.pidfile_path =  '/var/run/skynet/skynetd.pid'
        self.pidfile_timeout = 5
            
#########################################################
#
#  CORE
#
#########################################################  

    def run(self):
	logger.info("Initializing HVAC_init()")
	HVAC_init()
	logger.info("Cycling Relays")
	
	HVAC_SYSTEM_on()
	time.sleep(1)
	HVAC_SYSTEM_off()
	time.sleep(1)
	HVAC_FAN_on()
	HVAC_HEAT_on()
	HVAC_COOL_on()
	time.sleep(1)
	HVAC_FAN_off()
	HVAC_HEAT_off()
	HVAC_COOL_off()

	logger.info("Relay Tests OK, System OFF after init")

	logger.info("ENTERING MAIN LOOP")

#########################################################
#
#  CORE LOOPER
#
#########################################################  

	while True:
		#Main code goes here ...
            	#Note that logger level needs to be set to logging.DEBUG before this shows up in the logs
           	#logger.debug("Debug message")
            	logger.info("Main Routine")
		snmp_poller()
		write_prtg_snmp()
		uptime_poller()
		pi_hardware_poller()        
		poll_1wire_temps()
		if mode == 2:            		#HEAT
			ambient = tempTemps[0]
			logger.debug("Ambient: %s" % ambient)
			logger.debug("Set: %s" % setpoint)
		
			if ambient > setpoint + hyst_temp:
				HVAC_HEAT_off()
			elif ambient < setpoint - hyst_temp:
				HVAC_HEAT_on()
			else:
			    logger.debug("COMFORT RANGE")
    		time.sleep(10)
		upload_status()

#########################################################
#
#  RUN-ONCE INIT to instantiate App(), set up logger, 
#  and fork the daemon
#
#########################################################  

app = App()
logger = logging.getLogger("DaemonLog")
logger.setLevel(logging.WARN)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler = logging.FileHandler("/var/log/skynet/skynetd.log")
handler.setFormatter(formatter)
logger.addHandler(handler)

daemon_runner = runner.DaemonRunner(app)
#This ensures that the logger file handle does not get closed during daemonization
daemon_runner.daemon_context.files_preserve=[handler.stream]

try:
	daemon_runner.do_action()
except:
	print "CAUGHT SIGNAL"