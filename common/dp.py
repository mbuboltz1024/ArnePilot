#!/usr/bin/env python3.7
import subprocess
from common.params import Params
params = Params()

def get_last_modified():
  return Params().get('DragonLastModified', encoding='utf-8')

def is_online():
  return not subprocess.call(["ping", "-W", "4", "-c", "1", "117.28.245.92"])

def common_controller_update(lane_change_enabled):
  dragon_lat_ctrl = False if params.get("DragonLatCtrl", encoding='utf8') == "0" else True
  if dragon_lat_ctrl:
    lane_change_enabled = True if params.get("LaneChangeEnabled", encoding='utf8') == "1" else False
    if not lane_change_enabled:
      dragon_enable_steering_on_signal = True if params.get("DragonEnableSteeringOnSignal", encoding='utf8') == "1" else False
    else:
      dragon_enable_steering_on_signal = False
  else:
    dragon_enable_steering_on_signal = False
  return dragon_lat_ctrl, lane_change_enabled, dragon_enable_steering_on_signal

def common_controller_ctrl(enabled, dragon_lat_ctrl, dragon_enable_steering_on_signal, left_blinker, right_blinker, steer_req):
  if enabled:
    if dragon_enable_steering_on_signal:
      if left_blinker or right_blinker:
        steer_req = 0 if isinstance(steer_req, int) else False

    if not dragon_lat_ctrl:
      steer_req = 0 if isinstance(steer_req, int) else False

  return steer_req
