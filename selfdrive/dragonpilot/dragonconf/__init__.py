#!/usr/bin/env python3.7
from common.params import Params, put_nonblocking
import time
from math import floor
import os
import json

default_conf = {
  'DragonEnableDashcam': '0',
  'DragonEnableAutoShutdown': '1',
  'DragonAutoShutdownAt': '0', # in minute
  'DragonEnableSteeringOnSignal': '0',
  'DragonEnableLogger': '1',
  'DragonEnableUploader': '1',
  'DragonNoctuaMode': '0',
  'DragonAllowGas': '0',
  'DragonToyotaStockDSU': '0',
  'DragonLatCtrl': '1',
  'DragonUISpeed': '1',
  'DragonUIEvent': '1',
  'DragonUIMaxSpeed': '1',
  'DragonUIFace': '1',
  'DragonUIDev': '0',
  'DragonUIDevMini': '0',
  # 3rd party app
  'DragonEnableTomTom': '0',
  'DragonBootTomTom': '0',
  'DragonRunTomTom': '0',
  'DragonEnableAutonavi': '0',
  'DragonBootAutonavi': '0',
  'DragonRunAutonavi': '0',
  'DragonEnableAegis': '0',
  'DragonBootAegis': '0',
  'DragonRunAegis': '0',
  'DragonEnableMixplorer': '0',
  'DragonRunMixplorer': '0',
  'DragonSteeringMonitorTimer': '3', # 180 secs
  'DragonCameraOffset': '6',
  'DragonUIVolumeBoost': '0',
  'DragonGreyPandaMode': '0',
  'DragonDrivingUI': '1',
  'DragonDisplaySteeringLimitAlert': '1',
  'DragonChargingCtrl': '0',
  'DragonCharging': '70',
  'DragonDisCharging': '60',
  'DragonToyotaLaneDepartureWarning': '1',
  'DragonUILane': '1',
  'DragonUILead': '1',
  'DragonUIPath': '1',
  'DragonUIBlinker': '0',
  'DragonUIDMView': '0',
  'DragonEnableDriverMonitoring': '1',
  'DragonCarModel': '',
  'DragonEnableSlowOnCurve': '1',
  'DragonEnableLeadCarMovingAlert': '0',
  'DragonToyotaSnGMod': '0',
  'DragonWazeMode': '0',
  'DragonRunWaze': '0',
  'DragonEnableAutoLC': '0',
  'DragonAssistedLCMinMPH': '45',
  'DragonAutoLCMinMPH': '60',
  'DragonAutoLCDelay': '2',
  'DragonBTG': '0',
  'DragonBootHotspot': '0',
  'DragonAccelProfile': '0', # OFF = 0, ECO = 1, NORMAL = 2, SPORT = 3
  'DragonLastModified': str(floor(time.time())),
  'DragonEnableRegistration': '1',
  'DragonDynamicFollow': '0', # OFF = 0, LONG = 1, NORMAL = 2, SHORT = 3
  'DragonEnableGearCheck': '1',
  'DragonEnableTempMonitor': '1',
  'DragonAppAutoUpdate': '1',
  'DragonUpdating': '0',
  'DragonToyotaSngResponse': '0.0',
  'DragonCustomModel': '',
  'DragonLocale': 'en-US',
  'DragonUIScreenOffReversing': '0',
  'DragonEnableSRLearner': '1',
  'DragonEnableSteerBoost': '0',
  'DragonSteerBoostMin': '10', # percentage
  'DragonSteerBoostMax': '30', # percentage
  'DragonSteerBoostMinAt': '7.0',
  'DragonSteerBoostMaxAt': '15.0',
  'DragonDashcamHours': '24.0',
  'DragonUIScreenOffDriving': '0',
  'DragonEnableAutoUpdate': '1',
  'DragonUIBrightness': '0',
  'DragonEnableUploadOnMobile': '0',
  'DragonEnableUploadOnHotspot': '0',
  'DragonMaxSpeedLimit': '92',
  'DragonEnableRating': '1',
  'DragonEnableContALC' : '0',
  'DragonBlinkerOffTimer': '0',
}

deprecated_conf = {
}

deprecated_conf_invert = {
  #   'DragonDisableDriverSafetyCheck': True,
  #   'DragonTempDisableSteerOnSignal': False,
  #   'DragonDisableLogger': True,
  #   'DragonDisableUploader': True,
  #   'DragonBBUI': False
}

def dp_get_last_modified():
  return Params().get('DragonLastModified', encoding='utf-8').rstrip('\x00')

def dragonpilot_set_params(params):
  # # remove deprecated params
  # for old, new in deprecated_conf.items():
  #   if params.get(old) is not None:
  #     if new is not None:
  #       old_val = str(params.get(old))
  #       new_val = old_val
  #       # invert the value if true
  #       if old in deprecated_conf_invert and deprecated_conf_invert[old] is True:
  #         new_val = "1" if old_val == "0" else "0"
  #       put_nonblocking(new, new_val)
  #     params.delete(old)

  # set params
  for key, val in default_conf.items():
    if params.get(key) is None and key not in deprecated_conf:
      put_nonblocking(key, str(val))
  put_nonblocking('DragonSupportedCars', get_support_car_list())

def get_support_car_list():
  attrs = ['FINGERPRINTS', 'FW_VERSIONS']
  cars = dict()
  for car_folder in [x[0] for x in os.walk('/data/openpilot/selfdrive/car')]:
    try:
      car_name = car_folder.split('/')[-1]
      if car_name != "mock":
        names = []
        for attr in attrs:
          values = __import__('selfdrive.car.%s.values' % car_name, fromlist=[attr])
          if hasattr(values, attr):
            attr_values = getattr(values, attr)
          else:
            continue

          if isinstance(attr_values, dict):
            for f, v in attr_values.items():
              if f not in names:
                names.append(f)
          names.sort()
        cars[car_name] = names
    except (ImportError, IOError, ValueError):
      pass
  return json.dumps(cars)

if __name__ == "__main__":
  params = Params()
  params.manager_start()
  dragonpilot_set_params(params)
