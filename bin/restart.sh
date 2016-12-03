#!/bin/bash

echo Kill First
/opt/skynet/bin/killit.py

echo Now [Re]Starting
nohup sudo /opt/skynet/bin/skynetd.py start &
