#!/usr/bin/env python3.7
import os
import time
from common.params import Params
params = Params()
import cereal.messaging as messaging
from common.realtime import sec_since_boot
from common.dp import get_last_modified

def main():
  thermal_sock = messaging.sub_sock('thermal')
  secs = 0
  last_secs = None
  shutdown_at = 0
  started = False
  usb_online = False
  enabled = False
  last_enabled = None
  dp_last_modified = None
  while 1:
    cur_time = sec_since_boot()

    modified = get_last_modified()
    if dp_last_modified != modified:
      enabled = True if params.get("DragonEnableAutoShutdown", encoding='utf8') == '1' else False
      if enabled:
        try:
          secs = int(params.get("DragonAutoShutdownAt", encoding='utf8')) * 60
        except (TypeError, ValueError):
          secs = 0
      dp_last_modified = modified

    if last_enabled != enabled or last_secs != secs or started or usb_online:
      shutdown_at = cur_time + secs

    if enabled:
      msg = messaging.recv_sock(thermal_sock, wait=True)
      started = msg.thermal.started
      usb_online = msg.thermal.usbOnline

      if not started and not usb_online and secs > 0 and cur_time >= shutdown_at:
        os.system('LD_LIBRARY_PATH="" svc power shutdown')

    last_enabled = enabled
    last_secs = secs

    time.sleep(10)

if __name__ == "__main__":
  main()