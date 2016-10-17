#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# enable debugging
import cgi,cgitb
import RPi.GPIO as GPIO

#pigpio control
import pigpio

pi = pigpio.pi()
if not pi.connected:
	exit()


print("Content-Type: text/html;charset=utf-8")
print("\r\n\r\n")

#GPIO.setmode(GPIO.BCM) #old standard gpio

#CGI-BIN Initialization
cgitb.enable()    
form = cgi.FieldStorage()

subm = form.getvalue("submit")
clean = 0
relaySet = ["","","","",""]

if subm is None:
	print "Clean Run No Form Data"
	clean = 1

else:
	clean = 0
	relaySet[0] = form.getvalue('relay1')
	relaySet[1] = form.getvalue('relay2')
	relaySet[2] = form.getvalue('relay3')
	relaySet[3] = form.getvalue('relay4')
	relaySet[4] = form.getvalue('relay5')
	#print relaySet


#BODY & SCRIPT
pinList = [5,6,13,19,26]

relayCount = 0
relaysON = ["","","","",""]
relaysOFF = ["","","","",""]
for x in pinList:
	pi.set_mode(x, pigpio.OUTPUT)
	if clean != 1:
		if relaySet[relayCount] == "on":
			#print "on"
			pi.write(pinList[relayCount],0)
		elif relaySet[relayCount] == "off":
			#print "off"
			pi.write(pinList[relayCount],1)
		else:
			print "ERROR"
			exit()


	relayStat = pi.read(x)
	if relayStat == 0:
		relaysON[relayCount] = "checked='checked'"
	elif relayStat == 1:
		relaysOFF[relayCount] = "checked='checked'"
	else:
		exit()
	#relays[relayCount] = relayStatus
	relayCount += 1


print("<h1>TEST</h1><br>")
#HTML OUTPUT
print("<form id='dc' name='dc' method='post' action='/cgi-bin/testPIGPIO.py'>")
print("  <table width='600' border='1' cellspacing='0' cellpadding='2'>")
print("    <tr>")
print("      <th align='center' scope='col'>CHANNEL</th>")
print("      <th align='center' scope='col'>STATUS/CHANGE</th>")
print("    </tr>")
print("    <tr>")
print("      <td align='center'>HVAC_SYSTEM [0]</td>")
print("      <td align='center'><label><input type='radio' name='relay1' value='off' id='off' {of}/>Off</label><label><input type='radio' name='relay1' value='on' id='on' {on}/>On</label></td>".format(of=relaysOFF[0],on=relaysON[0]))
print("    </tr>")
print("    <tr>")
print("      <td align='center'>HVAC_FAN - [1]</td>")
print("      <td align='center'><label><input type='radio' name='relay2' value='off' id='off' {of}/>Off</label><label><input type='radio' name='relay2' value='on' id='on' {on}/>On</label></td>".format(of=relaysOFF[1],on=relaysON[1]))
print("    </tr>")
print("    <tr>")
print("      <td align='center'>HVAC_HEAT - [2]</td>")
print("      <td align='center'><label><input type='radio' name='relay3' value='off' id='off' {of}/>Off</label><label><input type='radio' name='relay3' value='on' id='on' {on}/>On</label></td>".format(of=relaysOFF[2],on=relaysON[2]))
print("    </tr>")
print("    <tr>")
print("      <td align='center'>HVAC_COOL - [3]</td>")
print("      <td align='center'><label><input type='radio' name='relay4' value='off' id='off' {of}/>Off</label><label><input type='radio' name='relay4' value='on' id='on' {on}/>On</label></td>".format(of=relaysOFF[3],on=relaysON[3]))
print("    </tr>")
print("    <tr>")
print("      <td align='center'>HVAC_AUTO - [4]</td>")
print("      <td align='center'><label><input type='radio' name='relay5' value='off' id='off' {of}/>Off (Manual)</label><label><input type='radio' name='relay5' value='on' id='on' {on}/>On (Automatic)</label></td>".format(of=relaysOFF[4],on=relaysON[4]))
print("    </tr>")
print("    <tr>")
print("      <td align='center'>ALL</td>")
print("      <td align='center'><label><input type='radio' name='allrelays' value='off' id='off' />Off</label><label><input type='radio' name='allrelays' value='on' id='on' />On</label></td>")
print("    </tr>")
print("    <tr>")
print("      <td align='center'>&nbsp;</td>")
print("      <td align='center'><input type='submit' name='submit' id='submit' value='Submit' /></td>")
print("    </tr>")
print("  </table>")
print("</form>")

