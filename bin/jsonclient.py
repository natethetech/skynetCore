#!/usr/bin/python

import requests

response = requests.get('http://192.168.1.250:8000/hvac/system',
                         auth=('webiopi', 'raspberry'))


response2 = requests.post('http://192.168.1.250:8000/hvac/system/1',
                         auth=('webiopi', 'raspberry'))


data = response.json()

print " GET:" + repr(response)
print "POST:" + repr(response2)


print repr(data)
