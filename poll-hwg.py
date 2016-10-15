#!/usr/bin/python

print "SKYNET-MASTER v1.01"
print "INITIALIZING\n\n"

#currently implements snmpv1 for compatibility with older HWg devices

from pysnmp.hlapi import *
import time
from ISStreamer.Streamer import Streamer
import re

import subprocess

#Measure init time
t1=time.clock()

#Initialize InitialState Streamers
print("Connecting SKYNET-TEMPS to InitialState Logger")
streamer = Streamer(bucket_name="SKYNET-TEMPS",
		bucket_key="8WC35WLXAAAY", 
		access_key="XgKetehqZ0ZOkLP91gLsddpj3HYUJK6Q")
print "Connecting SKYNET-PI to InitialState Logger"
pistreamer = Streamer(bucket_name="SKYNET-PI",
		bucket_key="J53VN6NNCYEJ",
		access_key="XgKetehqZ0ZOkLP91gLsddpj3HYUJK6Q")
#Set up SNMP
community = 'public'
port = 161
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
	['192.168.1.226','.1.3.6.1.4.1.21796.3.3.3.1.6.1','Outside Humid']]

#Run Polling Loops
print "\n\nTEMPERATURE Sensors"
print "--------------------------------------"
for host in range(len(tempHosts)):
	for (errorIndication,
     		errorStatus,
     		errorIndex,
     		varBinds) in getCmd(SnmpEngine(),
                          CommunityData(community, mpModel=0),              #mpModel=0 enables SNMPv1 (-v1)
                          UdpTransportTarget((tempHosts[host][0], 161)),
                          ContextData(),
                          ObjectType(ObjectIdentity(tempHosts[host][1])),   #Single Target OID
                          lookupMib=False):                                 #Do not resolve OID (-On)


    		if errorIndication:
        		print("ERROR\n")
			print(errorIndication)
        		break
    		elif errorStatus:
			print("ERROR\n")
        		print('%s at %s' % (errorStatus.prettyPrint(),
                            errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))
        		break
    		else:
			#PRIMARY ACTION HERE
			temperature = (float(varBinds[0][1])/10 * 1.8) + 32
			#Formatted console Output of gathered value
			print(repr(host) + ': ' + tempHosts[host][2] + ': ' + "%.2f" % temperature + 'F')
			tempHosts[host][3] = temperature
			#Send result to initialstate, heavily stripped and formatted for compatibility
			streamer.log(""+str(tempHosts[host][2]).strip()+"", round(float("%.2f" % temperature),4))
			print("   [SENT]")


#Writing & Logging Block

print "--------------------------------------\n\n"
#compute runtime
t2=time.clock()
print "Run Time: " + "%.2f" % (t2-t1) + ' seconds'
#write room sensor data to html
print "\n\nWriting Room Sensors HTML"
with open("/var/www/html/temps.html", "w") as text_file:
  for host in range(len(tempHosts)):
    text_file.write("[{0}]".format(tempHosts[host][3]))
print "Done."
print "--------------------------------------\n\n"

#get pi uptime, print it to console, send it to InitialState
output = subprocess.check_output(['cat','/proc/uptime'])
first = output.split(' ')
uptimeseconds = float(first[0])
print uptimeseconds
hours = uptimeseconds / 3600
print "Master Pi Up " + "%.2f" % (hours)  + " hours"
pistreamer.log("UPTIME",str("%.2f" % (hours))) 

#get pi gpu/cpu temps, then convert them to degrees F
output = subprocess.check_output(['/opt/skynet/piTemp.sh'])
first = output.split('=')
second = str(first[1]).split()
third = str(second[0]).split('\'')

gpu = (float(third[0]) * 1.8) + 32
cpu = (float(second[1]) / 1000 * 1.8) + 32
print "GPU: " + "%.2f" % gpu
print "CPU: " + "%.2f" % cpu

#write pi sensor data to html
print "\n\nWriting Pi Sensors HTML"
with open("/var/www/html/pitemps.html", "w") as text_file:
    text_file.write("[{0}]".format(gpu))
    text_file.write("[{0}]".format(cpu))
print "Done."
print "--------------------------------------\n\n"

#upload pi sensor data to initialstate
print "Writing Pi Sensors to InitialState"
pistreamer.log("Master Pi GPU", str(gpu))
pistreamer.log("Master Pi CPU", str(cpu))
print "Done."
print "--------------------------------------\n\n"

#Final time measure
t3=time.clock()

runtime = "" + '%.2f' % (t3-t1)

#Send run duration to InitialState
pistreamer.log("RUNTIME", str(runtime))

#Console output of run duration
print "Final Run Time: " + "%.2f" % (t3-t1) + ' seconds'
print "Done."


#COMPLETED
