#!/usr/bin/env python3.7
#
# courtesy of pjlao307 (https://github.com/pjlao307/)
# this is just his original implementation but
# in openpilot service form so it's always on
#
# with the highest bit rates, the video is approx. 0.5MB per second
# the default value is set to 2.56Mbps = 0.32MB per second
#
import os
import time
import datetime
import cereal.messaging as messaging
import subprocess
from selfdrive.swaglog import cloudlog
from common.params import Params, put_nonblocking
params = Params()
from common.realtime import sec_since_boot, DT_TRML
from common.dp import get_last_modified
import collections
import math

dashcam_videos_path = '/sdcard/dashcam/'
dashcam_duration = 60 # max is 180
bit_rates = 2560000 # max is 4000000
max_size_per_file = bit_rates/8*dashcam_duration # 2.56Mbps / 8 * 60 = 19.2MB per 60 seconds
freespace_limit = 0.15 # we start cleaning up footage when freespace is below 15%
shock_duration = 60

TYPE_DRIVING = 'driving'
TYPE_SHOCK = 'shock'

def main(gctx=None):
  retry = 0
  folder_exists = False
  dashcam_allowed = True
  # make sure dashcam folder exists
  while not folder_exists:
    try:
      if not os.path.exists(dashcam_videos_path):
        os.makedirs(dashcam_videos_path)
      else:
        folder_exists = True
        break
    except OSError:
      pass
    if retry >= 5:
      folder_exists = True
      dashcam_allowed = False

    retry += 1
    time.sleep(5)

  idlecam_enabled = False
  health_timeout = int(1000 * 2.5 * DT_TRML)  # 2.5x the expected health frequency
  health_sock = messaging.sub_sock('health', timeout=health_timeout)
  sensor_sock = messaging.sub_sock('sensorEvents')
  samples = collections.deque([])
  start_ts = None
  last_started = False


  dragon_dashcam_hours = 24. * 60 * 60
  max_storage = (max_size_per_file/dashcam_duration) * dragon_dashcam_hours
  dashcam_enabled = False
  last_ts = 0.
  last_modified = None
  sleep = 5

  thermal_sock = messaging.sub_sock('thermal')
  params.put("DragonDashcamImpactDetectStarted", "0")
  while dashcam_allowed:
    type = TYPE_DRIVING
    duration = dashcam_duration
    ts = sec_since_boot()
    if ts - last_ts >= 5.:
      modified = get_last_modified()
      if last_modified != modified:
        dashcam_enabled = True if params.get("DragonEnableDashcam", encoding='utf8') == "1" else False
        if dashcam_enabled:
          idlecam_enabled = True if params.get("DragonDashcamImpactDetect", encoding='utf8') == "1" else False
        else:
          idlecam_enabled = False
        try:
          dragon_dashcam_hours = float(params.get("DragonDashcamHours", encoding='utf8')) * 60 * 60
        except (TypeError, ValueError):
          dragon_dashcam_hours = 24. * 60 * 60
        max_storage = (max_size_per_file/dashcam_duration) * dragon_dashcam_hours

      last_modified = modified
      last_ts = ts

    health = messaging.recv_sock(health_sock, wait=False)
    started = True if health is not None and (health.health.ignitionLine or health.health.ignitionCan) else False
    record_started = False

    if last_started != started:
      params.put("DragonDashcamImpactDetectStarted", "0")
      samples.clear()

    if started:
      sleep = 5
      if dashcam_enabled:
        record_started = True
    else:
      if idlecam_enabled:
        sleep = 0.02
        sensor = messaging.recv_sock(sensor_sock, wait=False)
        if sensor is not None:
          for event in sensor.sensorEvents:
            # accelerometer
            if event.type == 1:
              acc_x = event.acceleration.v[0]
              acc_y = event.acceleration.v[1]
              acc_z = event.acceleration.v[2]
              g = math.sqrt(acc_x*acc_x+acc_y*acc_y+acc_z*acc_z)
              val = round(9.8-g,2)
              if len(samples) >= 250:
                avg_sample = round(sum(samples)/len(samples),2)
                if start_ts is None and abs(val - avg_sample) >= 0.3:
                  duration = shock_duration
                  type = TYPE_SHOCK
                  start_ts = ts
                  record_started = True
                  params.put("DragonDashcamImpactDetectStarted", "1")
                samples.pop()
              samples.appendleft(val)
        if start_ts is not None and ts - start_ts >= shock_duration-1:
          start_ts = None
          record_started = False
          params.put("DragonDashcamImpactDetectStarted", "0")

    last_started = started

    if record_started:
      now = datetime.datetime.now()
      file_name = now.strftime("%Y-%m-%d_%H-%M-%S")
      postfix = '_impact' if type == TYPE_SHOCK else ''
      os.system("screenrecord --bit-rate %s --time-limit %s %s%s%s.mp4 &" % (bit_rates, duration, dashcam_videos_path, file_name, postfix))
      start_time = time.time()
      try:
        used_spaces = get_used_spaces()
        last_used_spaces = used_spaces

        # we should clean up files here if use too much spaces
        # when used spaces greater than max available storage
        # or when free space is less than 10%
        # get health of board, log this in "thermal"
        msg = messaging.recv_sock(thermal_sock, wait=True)
        if used_spaces >= max_storage or (msg is not None and msg.thermal.freeSpace < freespace_limit):
          # get all the files in the dashcam_videos_path path
          files = [f for f in sorted(os.listdir(dashcam_videos_path)) if os.path.isfile(dashcam_videos_path + f)]
          for file in files:
            msg = messaging.recv_sock(thermal_sock, wait=True)
            # delete file one by one and once it has enough space for 1 video, we stop deleting
            if used_spaces - last_used_spaces < max_size_per_file or msg.thermal.freeSpace < freespace_limit:
              system("rm -fr %s" % (dashcam_videos_path + file))
              last_used_spaces = get_used_spaces()
            else:
              break
      except os.error as e:
        pass
      time_diff = time.time()-start_time
      # we start the process 1 second before screenrecord ended
      # to make sure there are no missing footage
      sleep_time = duration-1-time_diff
      if sleep_time >= 0.:
        time.sleep(sleep_time)
    else:
      time.sleep(sleep)

def get_used_spaces():
  return sum(os.path.getsize(dashcam_videos_path + f) for f in os.listdir(dashcam_videos_path) if os.path.isfile(dashcam_videos_path + f))

def system(cmd):
  try:
    # cloudlog.info("running %s" % cmd)
    subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
  except subprocess.CalledProcessError as e:
    cloudlog.event("running failed",
                   cmd=e.cmd,
                   output=e.output[-1024:],
                   returncode=e.returncode)

if __name__ == "__main__":
  main()