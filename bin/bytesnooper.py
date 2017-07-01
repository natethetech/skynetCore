#!/usr/bin/python
with open("mqtt-client.py") as fp:
    for i, line in enumerate(fp):
        if "\xe2" in line:
            print i, repr(line)

