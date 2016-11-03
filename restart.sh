#!/bin/bash

echo Kill First
/opt/skynet/killit.py

echo Now [Re]Starting
nohup sudo /opt/skynet/skynetd.py start &
