#!/usr/bin/python
# To kick off the script, run the following from the python directory:
#   PYTHONPATH=`pwd` python testdaemon.py start

#standard python libs
import sys
import logging
import time
from datetime import datetime
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
import thread

global cycleCount
cycleCount = 0
global cycles
cycles = 3
startTime = time.time()

GPIO.setmode(GPIO.BCM)    #set pin numbering to broadcom interface number

#third party libs
from daemon import runner

streamer = Streamer(bucket_name="SKYNET-TEMPS",bucket_key="8WC35WLXAAAY",access_key="XgKetehqZ0ZOkLP91gLsddpj3HYUJK6Q")
phonestreamer = Streamer(bucket_name="SKYNET-MOBILE",bucket_key="3T5JKNUXJUB9",access_key="XgKetehqZ0ZOkLP91gLsddpj3HYUJK6Q")
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
	19,    #Relay 3: COOL Control
	26,    #Ghost Relay: AUTOMATIC Control (1) [inverse is MANUAL (0)]
    ]

HVACpin_SYSTEM = 0
HVACpin_FAN = 1
HVACpin_HEAT = 2
HVACpin_COOL = 3
HVACpin_AUTO = 4

#thisPi = pigpio.pi()
#if not thisPi.connected:
#	#handle this error somehow
#	print "BAD CONNECT STATE"
#else:
#	print "Proceeding"

RELAY_ON = GPIO.LOW
RELAY_OFF = GPIO.HIGH

GPIO.setwarnings(False)

HVAC_status = [0,0,0,0,0]

HEAT_times = []   #last off   #last on
COOL_times = []

#rudimentary config for initial logic design
mode = 2           #0 off 1 fan 2 heat 3 cool
setpoint = 72      #rudimentary set temperature for initial logic design
hyst_temp = 4.0    #degrees over/under before trigger
hyst_time = 600    #seconds until next restart
HVAC_which = "BEDRM"

def main_streamer(text,value):
	streamer.log(text,value)

def pi_streamer(text,value):
	pistreamer.log(text,value)

def double_streamer(text,value):
	streamer.log(text,value)
	phonestreamer.log(text,value)
	pi_streamer(text,value)

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
	logger.debug("Audit Complete")
        upload_status()

def HVAC_goAuto():
	#test conditions, check relays, then change relays (turn off a/c for heat, etc) in a safe way
	logger.info("HVAC_goAuto()")
	HVAC_logic(True)
	HVAC_status[4] = 1	
	upload_status()

def HVAC_goManual():
	#test conditions, check relays, then change relays...?
	logger.info("HVAC_goManual()")
	HVAC_status[4] = 0
        upload_status()

#########################################################
#
#  Check Array against Actual and Adjust Array to Match
#
#########################################################  

def HVAC_audit():
	logger.info("HVAC_audit()")
	relayCounter = 0
	for x in pinList:
		HVAC_service_audit(relayCounter)
		relayCounter += 1

#########################################################
#
#  Send InitialState the current status of each component
#  0 = off     1 = on
#
#########################################################  

def upload_status():
        logger.debug("upload_status()")
	outStatus = ["OFF","ON"]
	ups = [0,0,0,0,0]
	statusCounter = 0
	global HVAC_status
	for x in range(len(HVAC_status)):
		ups[statusCounter] = float(HVAC_status[statusCounter]) + statusCounter + (float(statusCounter) / 10)
		statusCounter += 1
	double_streamer("HVAC_SYSTEM",HVAC_status[0])
	double_streamer("HVAC_FAN", HVAC_status[1])
	double_streamer("HVAC_HEAT", HVAC_status[2])
	double_streamer("HVAC_COOL", HVAC_status[3])
	double_streamer("HVAC_AUTO", HVAC_status[4])

        double_streamer("HVAC_SYSTEM_ADD",ups[0])
        double_streamer("HVAC_FAN_ADD", ups[1])
        double_streamer("HVAC_HEAT_ADD", ups[2])
        double_streamer("HVAC_COOL_ADD", ups[3])
        double_streamer("HVAC_AUTO_ADD", ups[4])
	HVAC_status_sum = 0
	statusCounter = 0
	for x in range(len(HVAC_status)):
		HVAC_status_sum += ups[statusCounter]
		statusCounter += 1
	double_streamer("HVAC_STATUS_SUM", HVAC_status_sum)
	logger.debug("***HVAC_status")
	logger.info("***HVAC_SYSTEM is %s" % outStatus[HVAC_status[0]]) 
	logger.info("***HVAC_FAN is %s" % outStatus[HVAC_status[1]]) 
	logger.info("***HVAC_HEAT is %s" % outStatus[HVAC_status[2]]) 
	logger.info("***HVAC_COOL is %s" % outStatus[HVAC_status[3]]) 
	logger.info("***HVAC_AUTO is %s" % outStatus[HVAC_status[4]]) 

#########################################################
#
#  HVAC_init
#  Set up each GPIO pin as output, off (high)
#
#########################################################  

def HVAC_init():
	logger.info("HVAC_init()")
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
#  HVAC_logic
#
############################################################

def HVAC_logic(override):
	logger.info("HVAC_logic()")
	#HVAC_audit()
	#FAN CYCLE 5 mins of every hour
	if datetime.now().strftime('%M') in ["00","01","02","03","04","05"]:
		HVAC_FAN_on()
	elif HVAC_isAuto() == True:
		HVAC_FAN_off()
	if HVAC_isAuto() or override:
		logger.info("Automatic Mode")
	        if mode == 2:                           	#HEAT
			HVAC_COOL_off()				#Because heat is on, turn off cool
			HVAC_service_audit(2)   		#CHECK THE HEAT RELAY, UPDATE STATUS
        		#ambient = tempTemps[0]			#CURRENTLY single-sensor set from the 1wire ambient sensor @ thermostat
        	        hostCounter=0
			found = 0
			for hostItem in range(len(tempHosts)):
				if (found == 0) and (HVAC_which in tempHosts[hostCounter][4]):
					ambient = tempHosts[hostCounter][3]
					double_streamer("HVAC_TargetAmbient","%.2f" % ambient)
					double_streamer("HVAC_which",hostCounter)
					double_streamer("HVAC_which_str",tempHosts[hostCounter][2])
					double_streamer("HVAC_SetPoint","%.2f" % setpoint)
					found = 1
				hostCounter += 1
			logger.debug("Ambient: %s" % ambient)
                	logger.debug("Set: %s" % setpoint)
                	if ambient > setpoint + hyst_temp:
                		logger.info("AUTO TURNING HEAT OFF")
				HVAC_HEAT_off()
                	elif ambient < setpoint - hyst_temp:
                        	logger.info("AUTO TURNING HEAT ON")
				HVAC_HEAT_on()
                	else:
                        	logger.debug("COMFORT RANGE")
	else:
		logger.info("Manual Mode, Doing Nothing Automatically")


############################################################
#
#  HVAC_SYSTEM_[off|on]
#  Primary control relay, used to "lock out" HEAT/COOL/FAN
#
############################################################

def HVAC_SYSTEM_off():
	logger.info("HVAC_SYSTEM_off()")
	#turn off relay 0
	logger.debug("HVAC_SYSTEM_off()")
	GPIO.output(pinList[0],RELAY_OFF)
	HVAC_status[0] = 0
        upload_status()
	
def HVAC_SYSTEM_on():
	#turn on relay 0
        logger.info("HVAC_SYSTEM_on()")
	logger.debug("HVAC_SYSTEM_on()")
	GPIO.output(pinList[0],RELAY_ON)
	HVAC_status[0] = 1
        upload_status()

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
        upload_status()

def HVAC_FAN_off():
	#turn off relay 1
        logger.debug("HVAC_FAN_off()")
	GPIO.output(pinList[1],RELAY_OFF)
	HVAC_status[1] = 0
        upload_status()

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
        upload_status()

def HVAC_HEAT_off():
	#turn off relay 2
        logger.debug("HVAC_HEAT_off()")
	GPIO.output(pinList[2],RELAY_OFF)
	HVAC_status[2] = 0
        upload_status()

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
        upload_status()

def HVAC_COOL_off():
	#turn off relay 3
        logger.debug("HVAC_COOL_off()")
	GPIO.output(pinList[3],RELAY_OFF)
	HVAC_status[3] = 0
        upload_status()

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
        upload_status()

def HVAC_AUTO_off():
        #turn off relay 4
        logger.debug("HVAC_AUTO_off()")
        GPIO.output(pinList[4],RELAY_OFF)
        HVAC_status[4] = 0
        upload_status()

def HVAC_isAuto():
	#HVAC_service_audit(4)      #update manual/auto service
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
	#logger.debug("file opened")
        lines = f.readlines()
	#logger.debug("lines read")
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
		logger.debug("Located both sensors OK")
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
		#with open("/var/www/html/1wire-1-RM_AMBIENT.html", "w") as text_file:
    		#	text_file.write("[{0}]".format(sensor1))
        	#with open("/var/www/html/1wire-2-DUCT.html", "w") as text_file:
                #	text_file.write("[{0}]".format(sensor2))
		#log to initialstate, both buckets
		if cycleCount == cycles:
			double_streamer("ThermostatAmbient","%.2f" % sensor1)
			double_streamer("ThermostatDUCT","%.2f" % sensor2)
			pi_streamer.log("ThermostatAmbient","%.2f" % sensor1)
			pi_streamer.log("ThermostatDUCT","%.2f" % sensor2)
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
                        #logger.error(errorIndication)
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
                        if cycleCount == cycles: 
				double_streamer(""+str(tempHosts[host][2]).strip()+"", round(float("%.2f" % temperature),4))
  
                    hostCount += 1

def write_runtime( before, after):
	diff = after-before
	if cycleCount == cycles:
		pi_streamer("CoreRuntime",diff)



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
        logger.info("write_prtg_snmp()")
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
        logger.info("uptime_poller()")
	#get pi uptime, print it to console, send it to InitialState
	output = subprocess.check_output(['cat','/proc/uptime'])
	first = output.split(' ')
	uptimeseconds = float(first[0])
	hours = uptimeseconds / 3600
	logger.info("Master Pi Up " + "%.2f" % (hours)  + " hours")
	if cycleCount == cycles:
		pi_streamer("UPTIME",str("%.2f" % (hours)))
	currentTime = time.time()
	processLifetime = (currentTime - startTime) / 3600
	logger.info("Skynet Daemon Process Lifespan (hours): %s" % processLifetime)
	if cycleCount == cycles:
		pi_streamer("Daemon-Uptime", str(processLifetime))


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
	#with open("/var/www/html/pitemps.html", "w") as text_file:
    	#	text_file.write("[{0}]".format(gpu))
    	#	text_file.write("[{0}]".format(cpu))
	#submit to initialstate
	if cycleCount == cycles:
		pi_streamer("Master Pi GPU", str(gpu))
		pi_streamer("Master Pi CPU", str(cpu))

#########################################################
#
#  Constructors for primary superclass
#
#########################################################  

class App():
    
    def __init__(self):
	print "INIT"
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
        logger.info("*****************************************************************")
        logger.info("*****************************************************************")
	logger.info("STARTUP INIT")
	logger.debug("Initializing HVAC_init()")
	HVAC_init()
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
		snmp_poller()           #Poll HWg Devices via SNMP
		#write_prtg_snmp()       #Write SNMP poll data for PRTG
		uptime_poller()		#Poll this pi's uptime
		pi_hardware_poller()    #Poll this pi's CPU/GPU
		poll_1wire_temps()	#Poll this unit's 1-wire sensors		
		#don't thread these, keep them linear
		HVAC_audit()
		HVAC_logic(False)	    	
		upload_status()
		#second iteration within the loop, again, don't thread these, keep them linear
		HVAC_audit()
		HVAC_logic(False)

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
		logger.warn("Heartbeat")
		global cycleCount
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
logger = logging.getLogger("DaemonLog")
logger.setLevel(logging.WARN)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler = logging.FileHandler("/var/log/skynet/skynetd.log")
handler.setFormatter(formatter)
logger.addHandler(handler)
#PASS the instance to the runner
daemon_runner = runner.DaemonRunner(app)
#PRESERVE: This ensures that the logger file handle does not get closed during daemonization
daemon_runner.daemon_context.files_preserve=[handler.stream]
#FORK the daemon and close the parent (and thus any link to the terminal, allowing the program to run without dying)
daemon_runner.do_action()
