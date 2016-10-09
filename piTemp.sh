#!/bin/bash
cpu=$(</sys/class/thermal/thermal_zone0/temp)
#GPU
/opt/vc/bin/vcgencmd measure_temp
#CPU
#echo "$((cpu/1000))"
cat /sys/class/thermal/thermal_zone0/temp
