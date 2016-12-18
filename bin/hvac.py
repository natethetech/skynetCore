#!/usr/bin/python

pinList = {}

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
    global pinList
    for line in lines:
        parsed = line.split('=')
        if len(parsed) == 2:
            pinList[parsed[0]] = parsed[1]

#########################################################
# GET
# getpin(which)  which=='heat'|'cool'|etc
#
#########################################################

def getpin(which):
    global pinList
    if pinList.has_key(which):
        return pinList[which]
    else:
        print "bad key"

def getpincount():
    global pinList
    return len(pinList)

parse_pinconfig(read_pinconfig())

#print getpincount()

print getpin('HEAT')
print getpin('heat')
