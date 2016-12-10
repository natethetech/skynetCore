#!/bin/bash
sudo rm -rf python_games
sudo rm -rv /usr/share/icons/*
sudo rm -rv /opt/vc/src/*
sudo rm -rv /usr/games/
sudo rm -rv /usr/share/squeak/
sudo rm -rv /usr/share/sounds/
sudo rm -rv /usr/share/wallpapers
sudo rm -rv /usr/share/themes
sudo rm -rv /usr/share/kde4
sudo rm -rv /usr/share/images/*

sudo find / -name "*.mp3" -type f -delete
sudo find / -name "*.wav" -type f -delete

sudo apt-get clean

