#!/usr/bin/python

import paho.mqtt.client as mqtt
import time
from datetime import date
hubpath = "/var/www/html/skynet/hub/"

#toddate = date(date.today()).isoformat()

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    f = open("/var/log/skynet/mqtt.log", "a")
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("#")

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
	localtime = time.asctime( time.localtime(time.time()) )
	#print "Local current time :", localtime
    	print(localtime+" :: "+msg.topic+" "+str(msg.payload))
	f = open("/var/log/skynet/mqtt.log", "a")
        topicString = str(msg.topic)
	payloadString = str(msg.payload)
	print topicString
	print payloadString

	if topicString[-4:] == "full":
		output = hubpath+topicString[:-4]+payloadString
		fullReader = open(output,"r")
		currently = fullReader.read()
		fullReader.close()
		if currently == "1":
			currently = "0";
		else: currently = "1"
		fullWriter = open(output,"w")
		fullWriter.write(currently)

	if topicString[-1:] == "w":
		w = open(hubpath+topicString[:-1]+"w.pwm","w")
		wPayload = payloadString
		print "W: " + wPayload
		w.write(wPayload)
		w.close()
	if topicString[-3:] == "rgb":
		r = open(hubpath+topicString[:-3]+"r.pwm","w")
		g = open(hubpath+topicString[:-3]+"g.pwm","w")
		b = open(hubpath+topicString[:-3]+"b.pwm","w")
		payload_split1 = payloadString.split("(")    #gives 'rgb' and 'rrr,ggg,bbb)'
		payload_split2 = payload_split1[1].split(")")   #gives 'rrr,ggg,bbb' and ???
		payload_split3 = payload_split2[0].split(",")   #should give 'rrr' and 'ggg' and 'bbb'
		rPayload = payload_split3[0]
		gPayload = payload_split3[1]
		bPayload = payload_split3[2]
		print "R: " + rPayload
		print "G: " + gPayload
		print "B: " + bPayload
		r.write(rPayload)
		g.write(gPayload)
		b.write(bPayload)

		r.close()
		g.close()
		b.close()
	f.write(localtime+" :: "+msg.topic+" :: "+str(msg.payload)+"\n")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect("192.168.1.250", 1883, 60)

# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.
client.loop_forever()
