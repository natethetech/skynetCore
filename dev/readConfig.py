#!/usr/bin/python
config_file = "/opt/skynet/conf/program.conf"

program_weekday = []
program_weekend = []
program = []

def read_config_raw():
        f = open(config_file, 'r')
        lines = f.readlines()
        f.close()
        return lines

def parse_config(lines):
	if "WEEKDAY" in lines[0]:    #FIRST LINE MUST BE WEEKDAY
	    line = 0
	    for x in range(8):          #four period setttings for each [weekday|weekend]
		thisblock=line
		for ticker in range(9):
		    one_var = lines[thisblock+ticker].split('=')
		    if len(one_var) > 1:
			one_var[0] = one_var[0].strip()
			one_var[1] = one_var[1].strip()
			if 'period' in one_var[0]:
				period = one_var[1]
			if 'name' in one_var[0]:
				name = one_var[1]
			if 'start_time' in one_var[0]:
				start_time_hhmm = one_var[1].split(':')
				hours = start_time_hhmm[0]
				minutes = start_time_hhmm[1]
			if 'function' in one_var[0]:
				function = one_var[1]
			if 'zones' in one_var[0]:
				zones = one_var[1].split(',')
			if 'set_temp' in one_var[0]:
				setTemp = one_var[1]
			if 'hyst_temp' in one_var[0]:
				hyst_temp = one_var[1]
			if 'hyst_time' in one_var[0]:
				hyst_time = one_var[1]
			else:
				pass
		    line += 1
		if (x < 4):
			program_weekday.insert(x,[name,[hours,minutes],function,zones,setTemp,hyst_temp,hyst_time])
		if (x >= 4):
			program_weekend.insert(x-4,[name,[hours,minutes],function,zones,setTemp,hyst_temp,hyst_time])
	for y in range(4):
		print program_weekday[y]
	for y in range(4):
		print program_weekend[y]
	global program
	program = [program_weekday,program_weekend]
	for y in range(4):
		print program[0][y]
	for y in range(4):
		print program[1][y]

def load_config():
	lines = read_config_raw()
	parse_config(lines)

load_config()
