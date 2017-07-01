#!/usr/bin/python
#skynetself.logger.py
#Implementation of the Logger module for skynet nodes


##### MAJOR TODO: implment findCaller function!!


import logging

class skynetloggerclass:

    #PUBLIC Logging functions (call THESE from other modules)

    def logwarn(self,thingToLog):
        self.logger.warn(thingToLog)

    def logerror(self,thingToLog):
        self.logger.error(thingToLog)

    def loginfo(self,thingToLog):
        self.logger.info(thingToLog)

    def logcrit(self,thingToLog):
        self.logger.critical(thingToLog)

    def logdebug(self,thingToLog):
        self.logger.debug(thingToLog)

    # ########################################################
    #
    # setloglevel()
    # sync the local loglevel value with the logging object value
    # called by getLogLevelConfig and any other function that
    # changes the local loglevel value
    #
    # ########################################################

    def setloglevel(self):
        if self.loglevel == "DEBUG":                   #Log extraneous crap you'd never normally want to see unless you're fixing something
            self.logger.setLevel(logging.DEBUG)
        elif self.loglevel == "WARNING":               #Log stuff that might be bad but might not be
            self.logger.setLevel(logging.WARNING)
        elif self.loglevel == "ERROR":                 #Log only when very bad things happen
            self.logger.setLevel(logging.ERROR)
        elif self.loglevel == "CRITICAL":              #Log only as the world ends
            self.logger.setLevel(logging.CRITICAL)
        else: #self.loglevel == "INFO" or other        #Common informative output, and the default if this decision chain fails
            self.logger.setLevel(logging.INFO)

    def getLogLevelConfig(self):
        try:
            with open("/opt/skynet/conf/loglevel.conf", "r") as text_file:
                loglevelconf = text_file.readlines()
                text_file.close()
        except:
            self.logerror("loglevelconf reader error!")
        #Step through logfile, omitting comment blocks
        for line in loglevelconf:
            if line[0] != '#':
                namevalsplit = line.split('=')
                for val in namevalsplit:
                    val = val.strip().upper()
                if namevalsplit[0] == "LOGLEVEL":
                    self.loglevel = namevalsplit[1]
        self.setloglevel()

    # ########################################################
    #
    # loggerLine()
    # returns a conveniently-sized line of characters set by
    # loggerLineExpander for logging
    # ########################################################

    loggerLineWidth = 65
    loggerLineExpander = ":"

    def loggerLine(self):
        return (loggerLineExpander * ((loggerLineWidth/len(loggerLineExpander))+1))[:loggerLineWidth]

    # ########################################################
    #
    # loggerFormat(string)
    #
    # Add spaces to the incoming string to ensure the formatting is consistent
    #
    # ########################################################


    def loggerFormat(self,incoming):
        spacersNeeded = self.loggerSpaces - len(incoming)
        if spacersNeeded < 0:
            self.logerror("FORMATTING ERROR! STRING IS TOO LONG! Current width of labels column: %s characters" % self.loggerSpaces)
        elif spacersNeeded == 0:
            self.logwarn("FORMATTING WARNING! STRING IS SAME WIDTH AS COLUMN! Current width of labels column: %s characters" % self.loggerSpaces)
        else:
            return (incoming.rjust(self.loggerSpaces) + ": ")

    ### MUST BE CALLED
    def __init__(self):
        self.loggerSpaces = 30
        self.loglevel = "INFO"
        self.logger = logging.getLogger("Skynet.d")
        self.getLogLevelConfig()
        formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
        handler = logging.FileHandler("/var/log/skynet/skynetd.log")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
