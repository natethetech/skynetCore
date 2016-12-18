#!/usr/bin/python

pinlist = {}
statuslist = {}

RELAY_ON = GPIO.LOW
RELAY_OFF = GPIO.HIGH

#########################################################
# FIRST
# read_pinconfig
#
#########################################################

def read_pinconfig():
    #try:
        with open("/opt/skynet/conf/iopins.conf", "r") as text_file:
            lines=text_file.readlines()
            text_file.close()
            return lines
    #except:
    #    print("heat_lastOff reader error!")

#########################################################
# SECOND
# read_parsepinconfig
#
#########################################################

def parse_pinconfig(lines):
    global pinlist
    for line in lines:
        parsed = line.split('=')
        if len(parsed) == 2:
            pinlist[parsed[0]] = parsed[1]
            statuslist[parsed[0]] = RELAY_OFF

#########################################################
# GETS
# getpin(which)  which=='heat'|'cool'|etc   returns INT
# GETPINCOUNT() returns INT
#
#########################################################

def getpin(which):
    global pinlist
    if pinlist.has_key(which.upper()):
        return pinlist[which.upper()]
    else:
        print "bad key"

def getpincount():
    global pinlist
    return len(pinlist)


############################################################
############################################################
############################################################
############################################################
############################################################

#HVAC_setstate replaces ALL complicated HVAC on/off commands from before
def HVAC_setstate(which,state):
    initstate = HVAC_getstate()
    if 'ENABLE' in state.upper():
        gpiostate = RELAY_ON
    elif 'DISABLE' in state.upper():
        gpiostate = RELAY_OFF
    if gpiostate != initstate:
        #change on pin, else don't do anything
        GPIO.output(getpin(which.upper()),gpiostate)
        HVAC_writer(which,state)   #pass both variables to the writer to compute on and off times and write to file
    else:
        print "i dont do anything yet"

def HVAC_getstate(which):
    pinstat = GPIO.input(getpin(which.upper()))
    if pinstat:
        pinstatus = GPIO.LOW
    else:
        pinstatus = GPIO.HIGH
    return pinstatus #0 off 1 on RELAYS ONLY

def HVAC_writer(which,state):
    timeNow = time.time()
    if timeNow-startTime >= 60:   #guaranteed 60 seconds of "init"
        HEAT_times[1] = timeNow   #1 index is time-since-ON #0 is time-since-OFF
        HEAT_runtimes[0] = round(timeNow - HEAT_times[0],1)








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
# HVAC_init()
#
# Set up each GPIO pin as output, off (high)
#
#########################################################

def HVAC_init():
    parse_pinconfig(read_pinconfig())
    for unit,pin in pinlist.items():
        GPIO.setup(pin, GPIO.OUT)
        #Turn off the relay by default
        GPIO.output(pin,RELAY_OFF)
