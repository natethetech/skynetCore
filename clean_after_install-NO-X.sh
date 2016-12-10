#!/bin/bash
sudo apt-get autoremove x11-common
sudo apt-get autoremove midori
sudo apt-get autoremove lxde-icon-theme
#sudo apt-get autoremove omxplayer

sudo apt-get autoremove scratch
sudo apt-get autoremove dillo
sudo apt-get autoremove xpdf
sudo apt-get autoremove galculator
sudo apt-get autoremove netsurf-common
sudo apt-get autoremove netsurf-gtk
sudo apt-get autoremove idle-python3.2

sudo apt-get autoremove lxde-common
sudo apt-get autoremove lxdeterminal
sudo apt-get autoremove hicolor-icon-theme

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

sudo apt-get autoremove
sudo apt-get clean

