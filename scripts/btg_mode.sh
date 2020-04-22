#!/usr/bin/bash

mode=$1
if [ $1 -eq 1 ]; then
  printf %s "1" > /data/params/d/DragonBTG
fi
if [ $1 -eq 0 ]; then
  printf %s "0" > /data/params/d/DragonBTG
fi

rm -rf /data/openpilot/selfdrive/boardd/boardd && reboot