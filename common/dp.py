#!/usr/bin/env python3.7
import subprocess
from common.params import Params
params = Params()

def get_last_modified():
  return Params().get('DragonLastModified', encoding='utf-8')

def is_online():
  return not subprocess.call(["ping", "-W", "4", "-c", "1", "117.28.245.92"])

def common_controller_update():
  dragon_lat_ctrl = False if params.get("DragonLatCtrl", encoding='utf8') == "0" else True
  if dragon_lat_ctrl:
    dragon_enable_steering_on_signal = True if (params.get("DragonEnableSteeringOnSignal", encoding='utf8') == "1" and params.get("LaneChangeEnabled", encoding='utf8') == "0") else False
    if dragon_enable_steering_on_signal:
      try:
        dragon_blinker_off_timer = float(params.get("DragonBlinkerOffTimer", encoding='utf8')) * 100
      except (TypeError, ValueError):
        dragon_blinker_off_timer = 0
    else:
      dragon_blinker_off_timer = 0
  else:
    dragon_enable_steering_on_signal = False
    dragon_blinker_off_timer = 0
  return dragon_lat_ctrl, dragon_enable_steering_on_signal, dragon_blinker_off_timer

def common_controller_ctrl(enabled, dragon_lat_ctrl, dragon_enable_steering_on_signal, blinker_on, steer_req):
  if enabled:
    if (dragon_enable_steering_on_signal and blinker_on) or not dragon_lat_ctrl:
      steer_req = 0 if isinstance(steer_req, int) else False

  return steer_req
