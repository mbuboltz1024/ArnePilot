import numpy as np
from cereal import car
from selfdrive.config import Conversions as CV
from selfdrive.car.interfaces import CarStateBase
from opendbc.can.parser import CANParser
from opendbc.can.can_define import CANDefine
from selfdrive.car.volkswagen.values import DBC, CANBUS, NWL, TRANS, GEAR, BUTTON_STATES, CarControllerParams


class CarState(CarStateBase):
  def __init__(self, CP):
    super().__init__(CP)
    can_define = CANDefine(DBC[CP.carFingerprint]['pt'])

    if CP.safetyModel == car.CarParams.SafetyModel.volkswagenPq:
      # Configure for PQ35/PQ46/NMS network messaging
      self.get_can_parser = self.get_pq_can_parser
      self.get_cam_can_parser = self.get_pq_cam_can_parser
      self.update = self.update_pq
      if CP.transmissionType == TRANS.automatic:
        self.shifter_values = can_define.dv["Getriebe_1"]['Waehlhebelposition__Getriebe_1_']
    else:
      # Configure for MQB network messaging (default)
      self.get_can_parser = self.get_mqb_can_parser
      self.get_cam_can_parser = self.get_mqb_cam_can_parser
      self.update = self.update_mqb
      if CP.transmissionType == TRANS.automatic:
        self.shifter_values = can_define.dv["Getriebe_11"]['GE_Fahrstufe']
      elif CP.transmissionType == TRANS.direct:
        self.shifter_values = can_define.dv["EV_Gearshift"]['GearPosition']

    self.buttonStates = BUTTON_STATES.copy()

  def update_mqb(self, pt_cp, cam_cp, acc_cp, trans_type):
    ret = car.CarState.new_message()
    # Update vehicle speed and acceleration from ABS wheel speeds.
    ret.wheelSpeeds.fl = pt_cp.vl["ESP_19"]['ESP_VL_Radgeschw_02'] * CV.KPH_TO_MS
    ret.wheelSpeeds.fr = pt_cp.vl["ESP_19"]['ESP_VR_Radgeschw_02'] * CV.KPH_TO_MS
    ret.wheelSpeeds.rl = pt_cp.vl["ESP_19"]['ESP_HL_Radgeschw_02'] * CV.KPH_TO_MS
    ret.wheelSpeeds.rr = pt_cp.vl["ESP_19"]['ESP_HR_Radgeschw_02'] * CV.KPH_TO_MS

    ret.vEgoRaw = float(np.mean([ret.wheelSpeeds.fl, ret.wheelSpeeds.fr, ret.wheelSpeeds.rl, ret.wheelSpeeds.rr]))
    ret.vEgo, ret.aEgo = self.update_speed_kf(ret.vEgoRaw)

    ret.standstill = ret.vEgoRaw < 0.1

    # Update steering angle, rate, yaw rate, and driver input torque. VW send
    # the sign/direction in a separate signal so they must be recombined.
    ret.steeringAngle = pt_cp.vl["LWI_01"]['LWI_Lenkradwinkel'] * (1, -1)[int(pt_cp.vl["LWI_01"]['LWI_VZ_Lenkradwinkel'])]
    ret.steeringRate = pt_cp.vl["LWI_01"]['LWI_Lenkradw_Geschw'] * (1, -1)[int(pt_cp.vl["LWI_01"]['LWI_VZ_Lenkradwinkel'])]
    ret.steeringTorque = pt_cp.vl["EPS_01"]['Driver_Strain'] * (1, -1)[int(pt_cp.vl["EPS_01"]['Driver_Strain_VZ'])]
    ret.steeringPressed = abs(ret.steeringTorque) > CarControllerParams.STEER_DRIVER_ALLOWANCE
    ret.yawRate = pt_cp.vl["ESP_02"]['ESP_Gierrate'] * (1, -1)[int(pt_cp.vl["ESP_02"]['ESP_VZ_Gierrate'])] * CV.DEG_TO_RAD

    # Update gas, brakes, and gearshift.
    ret.gas = pt_cp.vl["Motor_20"]['MO_Fahrpedalrohwert_01'] / 100.0
    ret.gasPressed = ret.gas > 0
    ret.brake = pt_cp.vl["ESP_05"]['ESP_Bremsdruck'] / 250.0  # FIXME: this is pressure in Bar, not sure what OP expects
    ret.brakePressed = bool(pt_cp.vl["ESP_05"]['ESP_Fahrer_bremst'])
    ret.brakeLights = bool(pt_cp.vl["ESP_05"]['ESP_Status_Bremsdruck'])

    # Additional safety checks performed in CarInterface.
    self.parkingBrakeSet = bool(pt_cp.vl["Kombi_01"]['KBI_Handbremse'])  # FIXME: need to include an EPB check as well
    ret.espDisabled = pt_cp.vl["ESP_21"]['ESP_Tastung_passiv'] != 0

    # Update gear and/or clutch position data.
    if trans_type == TRANS.automatic:
      ret.gearShifter = self.parse_gear_shifter(self.shifter_values.get(pt_cp.vl["Getriebe_11"]['GE_Fahrstufe'], None))
    elif trans_type == TRANS.direct:
      ret.gearShifter = self.parse_gear_shifter(self.shifter_values.get(pt_cp.vl["EV_Gearshift"]['GearPosition'], None))
    elif trans_type == TRANS.manual:
      ret.clutchPressed = not pt_cp.vl["Motor_14"]['MO_Kuppl_schalter']
      reverse_light = bool(pt_cp.vl["Gateway_72"]['BCM1_Rueckfahrlicht_Schalter'])
      # TODO: verify this synthesis has the desired behavior.
      # In particular, should we neutral disengage during normal gear changes?
      # Also, what happens if we're rolling backwards with the clutch pressed
      # in a gear other than reverse?
      if reverse_light:
        ret.gearShifter = GEAR.reverse
      elif ret.standstill and self.parkingBrakeSet:
        ret.gearShifter = GEAR.park
      elif ret.clutchPressed:
        ret.gearShifter = GEAR.neutral
      else:
        ret.gearShifter = GEAR.drive

    # Update door and trunk/hatch lid open status.
    ret.doorOpen = any([pt_cp.vl["Gateway_72"]['ZV_FT_offen'],
                        pt_cp.vl["Gateway_72"]['ZV_BT_offen'],
                        pt_cp.vl["Gateway_72"]['ZV_HFS_offen'],
                        pt_cp.vl["Gateway_72"]['ZV_HBFS_offen'],
                        pt_cp.vl["Gateway_72"]['ZV_HD_offen']])

    # Update seatbelt fastened status.
    ret.seatbeltUnlatched = False if pt_cp.vl["Airbag_02"]["AB_Gurtschloss_FA"] == 3 else True

    # Update driver preference for metric. VW stores many different unit
    # preferences, including separate units for for distance vs. speed.
    # We use the speed preference for OP.
    self.displayMetricUnits = not pt_cp.vl["Einheiten_01"]["KBI_MFA_v_Einheit_02"]

    # Update ACC radar status.
    accStatus = pt_cp.vl["TSK_06"]['TSK_Status']
    if accStatus == 2:
      # ACC okay and enabled, but not currently engaged
      ret.cruiseState.available = True
      ret.cruiseState.enabled = False
    elif accStatus in [3, 4, 5]:
      # ACC okay and enabled, currently engaged and regulating speed (3) or engaged with driver accelerating (4) or overrun (5)
      ret.cruiseState.available = True
      ret.cruiseState.enabled = True
    else:
      # ACC okay but disabled (1), or a radar visibility or other fault/disruption (6 or 7)
      ret.cruiseState.available = False
      ret.cruiseState.enabled = False

    # Update ACC setpoint. When the setpoint is zero or there's an error, the
    # radar sends a set-speed of ~90.69 m/s / 203mph.
    ret.cruiseState.speed = acc_cp.vl["ACC_02"]['SetSpeed']
    if ret.cruiseState.speed > 90:
      ret.cruiseState.speed = 0

    # Update control button states for turn signals and ACC controls.
    self.buttonStates["accelCruise"] = bool(pt_cp.vl["GRA_ACC_01"]['GRA_Tip_Hoch'])
    self.buttonStates["decelCruise"] = bool(pt_cp.vl["GRA_ACC_01"]['GRA_Tip_Runter'])
    self.buttonStates["cancel"] = bool(pt_cp.vl["GRA_ACC_01"]['GRA_Abbrechen'])
    self.buttonStates["setCruise"] = bool(pt_cp.vl["GRA_ACC_01"]['GRA_Tip_Setzen'])
    self.buttonStates["resumeCruise"] = bool(pt_cp.vl["GRA_ACC_01"]['GRA_Tip_Wiederaufnahme'])
    self.buttonStates["gapAdjustCruise"] = bool(pt_cp.vl["GRA_ACC_01"]['GRA_Verstellung_Zeitluecke'])
    ret.leftBlinker = bool(pt_cp.vl["Gateway_72"]['BH_Blinker_li'])
    ret.rightBlinker = bool(pt_cp.vl["Gateway_72"]['BH_Blinker_re'])

    # Read ACC hardware button type configuration info that has to pass thru
    # to the radar. Ends up being different for steering wheel buttons vs
    # third stalk type controls.
    self.graHauptschalter = pt_cp.vl["GRA_ACC_01"]['GRA_Hauptschalter']
    self.graTypHauptschalter = pt_cp.vl["GRA_ACC_01"]['GRA_Typ_Hauptschalter']
    self.graButtonTypeInfo = pt_cp.vl["GRA_ACC_01"]['GRA_ButtonTypeInfo']
    self.graTipStufe2 = pt_cp.vl["GRA_ACC_01"]['GRA_Tip_Stufe_2']
    self.graTyp468 = pt_cp.vl["GRA_ACC_01"]['GRA_Typ468']
    # Pick up the GRA_ACC_01 CAN message counter so we can sync to it for
    # later cruise-control button spamming.
    self.graMsgBusCounter = pt_cp.vl["GRA_ACC_01"]['COUNTER']

    # Check to make sure the electric power steering rack is configured to
    # accept and respond to HCA_01 messages and has not encountered a fault.
    self.steeringFault = not pt_cp.vl["EPS_01"]["HCA_Ready"]

    return ret

  def update_pq(self, pt_cp, cam_cp, acc_cp, trans_type):
    ret = car.CarState.new_message()
    # Update vehicle speed and acceleration from ABS wheel speeds.
    ret.wheelSpeeds.fl = pt_cp.vl["Bremse_3"]['Radgeschw__VL_4_1'] * CV.KPH_TO_MS
    ret.wheelSpeeds.fr = pt_cp.vl["Bremse_3"]['Radgeschw__VR_4_1'] * CV.KPH_TO_MS
    ret.wheelSpeeds.rl = pt_cp.vl["Bremse_3"]['Radgeschw__HL_4_1'] * CV.KPH_TO_MS
    ret.wheelSpeeds.rr = pt_cp.vl["Bremse_3"]['Radgeschw__HR_4_1'] * CV.KPH_TO_MS

    ret.vEgoRaw = float(np.mean([ret.wheelSpeeds.fl, ret.wheelSpeeds.fr, ret.wheelSpeeds.rl, ret.wheelSpeeds.rr]))
    ret.vEgo, ret.aEgo = self.update_speed_kf(ret.vEgoRaw)

    ret.standstill = ret.vEgoRaw < 0.1

    # Update steering angle, rate, yaw rate, and driver input torque. VW send
    # the sign/direction in a separate signal so they must be recombined.
    ret.steeringAngle = pt_cp.vl["Lenkhilfe_3"]['LH3_BLW'] * (1, -1)[int(pt_cp.vl["Lenkhilfe_3"]['LH3_BLWSign'])]
    ret.steeringRate = pt_cp.vl["Lenkwinkel_1"]['Lenkradwinkel_Geschwindigkeit'] * (1, -1)[int(pt_cp.vl["Lenkwinkel_1"]['Lenkradwinkel_Geschwindigkeit_S'])]
    ret.steeringTorque = pt_cp.vl["Lenkhilfe_3"]['LH3_LM'] * (1, -1)[int(pt_cp.vl["Lenkhilfe_3"]['LH3_LMSign'])]
    ret.steeringPressed = abs(ret.steeringTorque) > CarControllerParams.STEER_DRIVER_ALLOWANCE
    ret.yawRate = pt_cp.vl["Bremse_5"]['Giergeschwindigkeit'] * (1, -1)[int(pt_cp.vl["Bremse_5"]['Vorzeichen_der_Giergeschwindigk'])] * CV.DEG_TO_RAD

    # Update gas, brakes, and gearshift.
    ret.gas = pt_cp.vl["Motor_3"]['Fahrpedal_Rohsignal'] / 100.0
    ret.gasPressed = ret.gas > 0
    ret.brake = pt_cp.vl["Bremse_5"]['Bremsdruck'] / 250.0  # FIXME: this is pressure in Bar, not sure what OP expects
    ret.brakePressed = bool(pt_cp.vl["Motor_2"]['Bremstestschalter'])
    ret.brakeLights = bool(pt_cp.vl["Motor_2"]['Bremslichtschalter'])

    # Additional safety checks performed in CarInterface.
    self.parkingBrakeSet = bool(pt_cp.vl["Kombi_1"]['Bremsinfo'])  # FIXME: need to include an EPB check as well
    ret.espDisabled = bool(pt_cp.vl["Bremse_1"]['ESP_Passiv_getastet'])

    # Update gear and/or clutch position data.
    if trans_type == TRANS.automatic:
      ret.gearShifter = self.parse_gear_shifter(self.shifter_values.get(pt_cp.vl["Getriebe_1"]['Waehlhebelposition__Getriebe_1_'], None))
    elif trans_type == TRANS.manual:
      ret.clutchPressed = not pt_cp.vl["Motor_1"]['Kupplungsschalter']
      reverse_light = bool(pt_cp.vl["Gate_Komf_1"]['GK1_Rueckfahr'])
      # TODO: verify this synthesis has the desired behavior.
      # In particular, should we neutral disengage during normal gear changes?
      # Also, what happens if we're rolling backwards with the clutch pressed
      # in a gear other than reverse?
      if reverse_light:
        ret.gearShifter = GEAR.reverse
      elif ret.standstill and self.parkingBrakeSet:
        ret.gearShifter = GEAR.park
      elif ret.clutchPressed:
        ret.gearShifter = GEAR.neutral
      else:
        ret.gearShifter = GEAR.drive

    # Update door and trunk/hatch lid open status.
    # TODO: need to locate signals for other three doors if possible
    ret.doorOpen = bool(pt_cp.vl["Gate_Komf_1"]['GK1_Fa_Tuerkont'])

    # Update seatbelt fastened status.
    ret.seatbeltUnlatched = not bool(pt_cp.vl["Airbag_1"]["Gurtschalter_Fahrer"])

    # Update driver preference for metric. VW stores many different unit
    # preferences, including separate units for for distance vs. speed.
    # We use the speed preference for OP.
    self.displayMetricUnits = not pt_cp.vl["Einheiten_1"]["MFA_v_Einheit_02"]

    # Update ACC radar status.
    # FIXME: This is unfinished and not fully correct, need to improve further
    ret.cruiseState.available = bool(pt_cp.vl["GRA_neu"]['Hauptschalter'])
    ret.cruiseState.enabled = True if pt_cp.vl["Motor_2"]['GRA_Status'] in [1, 2] else False

    # Update ACC setpoint. When the setpoint reads as 255, the driver has not
    # yet established an ACC setpoint, so treat it as zero.
    ret.cruiseState.speed = acc_cp.vl["ACC_GRA_Anziege"]['ACA_V_Wunsch'] * CV.KPH_TO_MS
    if ret.cruiseState.speed > 70:  # 255 kph in m/s == no current setpoint
      ret.cruiseState.speed = 0

    # Update control button states for turn signals and ACC controls.
    self.buttonStates["accelCruise"] = bool(pt_cp.vl["GRA_neu"]['Kurz_Tip_up']) or bool(pt_cp.vl["GRA_neu"]['Lang_Tip_up'])
    self.buttonStates["decelCruise"] = bool(pt_cp.vl["GRA_neu"]['Kurz_Tip_down']) or bool(pt_cp.vl["GRA_neu"]['Lang_Tip_down'])
    self.buttonStates["cancel"] = bool(pt_cp.vl["GRA_neu"]['Abbrechen'])
    self.buttonStates["setCruise"] = bool(pt_cp.vl["GRA_neu"]['Setzen'])
    self.buttonStates["resumeCruise"] = bool(pt_cp.vl["GRA_neu"]['Wiederaufnahme'])
    self.buttonStates["gapAdjustCruise"] = bool(pt_cp.vl["GRA_neu"]['Zeitlueckenverstellung'])
    ret.leftBlinker = bool(pt_cp.vl["Gate_Komf_1"]['GK1_Blinker_li'])
    ret.rightBlinker = bool(pt_cp.vl["Gate_Komf_1"]['GK1_Blinker_re'])

    # Read ACC hardware button type configuration info that has to pass thru
    # to the radar. Ends up being different for steering wheel buttons vs
    # third stalk type controls.
    # TODO: Check to see what info we need to passthru and spoof on PQ
    self.graHauptschalter = pt_cp.vl["GRA_neu"]['Hauptschalter']
    self.graTypHauptschalter = False
    self.graButtonTypeInfo = False
    self.graTipStufe2 = False
    # Pick up the GRA_ACC_01 CAN message counter so we can sync to it for
    # later cruise-control button spamming.
    # FIXME: will need msg counter and checksum algo to spoof GRA_neu
    self.graMsgBusCounter = 0

    # Check to make sure the electric power steering rack is configured to
    # accept and respond to HCA_01 messages and has not encountered a fault.
    self.steeringFault = pt_cp.vl["Lenkhilfe_2"]['LH2_Sta_HCA'] not in [3, 5]

    return ret

  @staticmethod
  def get_mqb_can_parser(CP):
    signals = [
      # sig_name, sig_address, default
      ("LWI_Lenkradwinkel", "LWI_01", 0),           # Absolute steering angle
      ("LWI_VZ_Lenkradwinkel", "LWI_01", 0),        # Steering angle sign
      ("LWI_Lenkradw_Geschw", "LWI_01", 0),         # Absolute steering rate
      ("LWI_VZ_Lenkradw_Geschw", "LWI_01", 0),      # Steering rate sign
      ("ESP_VL_Radgeschw_02", "ESP_19", 0),         # ABS wheel speed, front left
      ("ESP_VR_Radgeschw_02", "ESP_19", 0),         # ABS wheel speed, front right
      ("ESP_HL_Radgeschw_02", "ESP_19", 0),         # ABS wheel speed, rear left
      ("ESP_HR_Radgeschw_02", "ESP_19", 0),         # ABS wheel speed, rear right
      ("ESP_Gierrate", "ESP_02", 0),                # Absolute yaw rate
      ("ESP_VZ_Gierrate", "ESP_02", 0),             # Yaw rate sign
      ("ZV_FT_offen", "Gateway_72", 0),             # Door open, driver
      ("ZV_BT_offen", "Gateway_72", 0),             # Door open, passenger
      ("ZV_HFS_offen", "Gateway_72", 0),            # Door open, rear left
      ("ZV_HBFS_offen", "Gateway_72", 0),           # Door open, rear right
      ("ZV_HD_offen", "Gateway_72", 0),             # Trunk or hatch open
      ("BH_Blinker_li", "Gateway_72", 0),           # Left turn signal on
      ("BH_Blinker_re", "Gateway_72", 0),           # Right turn signal on
      ("AB_Gurtschloss_FA", "Airbag_02", 0),        # Seatbelt status, driver
      ("AB_Gurtschloss_BF", "Airbag_02", 0),        # Seatbelt status, passenger
      ("ESP_Fahrer_bremst", "ESP_05", 0),           # Brake pedal pressed
      ("ESP_Status_Bremsdruck", "ESP_05", 0),       # Brakes applied
      ("ESP_Bremsdruck", "ESP_05", 0),              # Brake pressure applied
      ("MO_Fahrpedalrohwert_01", "Motor_20", 0),    # Accelerator pedal value
      ("Driver_Strain", "EPS_01", 0),               # Absolute driver torque input
      ("Driver_Strain_VZ", "EPS_01", 0),            # Driver torque input sign
      ("HCA_Ready", "EPS_01", 0),                   # Steering rack HCA support configured
      ("ESP_Tastung_passiv", "ESP_21", 0),          # Stability control disabled
      ("KBI_MFA_v_Einheit_02", "Einheiten_01", 0),  # MPH vs KMH speed display
      ("KBI_Handbremse", "Kombi_01", 0),            # Manual handbrake applied
      ("TSK_Status", "TSK_06", 0),                  # ACC engagement status from drivetrain coordinator
      ("GRA_Hauptschalter", "GRA_ACC_01", 0),       # ACC button, on/off
      ("GRA_Abbrechen", "GRA_ACC_01", 0),           # ACC button, cancel
      ("GRA_Tip_Setzen", "GRA_ACC_01", 0),          # ACC button, set
      ("GRA_Tip_Hoch", "GRA_ACC_01", 0),            # ACC button, increase or accel
      ("GRA_Tip_Runter", "GRA_ACC_01", 0),          # ACC button, decrease or decel
      ("GRA_Tip_Wiederaufnahme", "GRA_ACC_01", 0),  # ACC button, resume
      ("GRA_Verstellung_Zeitluecke", "GRA_ACC_01", 0),  # ACC button, time gap adj
      ("GRA_Typ_Hauptschalter", "GRA_ACC_01", 0),   # ACC main button type
      ("GRA_Tip_Stufe_2", "GRA_ACC_01", 0),         # unknown related to stalk type
      ("GRA_Typ468", "GRA_ACC_01", 0),              # Set/Resume button behavior as overloaded coast/accel??
      ("GRA_ButtonTypeInfo", "GRA_ACC_01", 0),      # unknown related to stalk type
      ("COUNTER", "GRA_ACC_01", 0),                 # GRA_ACC_01 CAN message counter
    ]

    checks = [
      # sig_address, frequency
      ("LWI_01", 100),            # From J500 Steering Assist with integrated sensors
      ("EPS_01", 100),            # From J500 Steering Assist with integrated sensors
      ("ESP_19", 100),            # From J104 ABS/ESP controller
      ("ESP_05", 50),             # From J104 ABS/ESP controller
      ("ESP_21", 50),             # From J104 ABS/ESP controller
      ("Motor_20", 50),           # From J623 Engine control module
      ("TSK_06", 50),             # From J623 Engine control module
      ("GRA_ACC_01", 33),         # From J??? steering wheel control buttons
      ("Gateway_72", 10),         # From J533 CAN gateway (aggregated data)
      ("Airbag_02", 5),           # From J234 Airbag control module
      ("Kombi_01", 2),            # From J285 Instrument cluster
      ("Einheiten_01", 1),        # From J??? not known if gateway, cluster, or BCM
    ]

    if CP.transmissionType == TRANS.automatic:
      signals += [("GE_Fahrstufe", "Getriebe_11", 0)]  # Auto trans gear selector position
      checks += [("Getriebe_11", 20)]  # From J743 Auto transmission control module
    elif CP.transmissionType == TRANS.direct:
      signals += [("GearPosition", "EV_Gearshift", 0)]  # EV gear selector position
      checks += [("EV_Gearshift", 10)]  # From J??? unknown EV control module
    elif CP.transmissionType == TRANS.manual:
      signals += [("MO_Kuppl_schalter", "Motor_14", 0),  # Clutch switch
                  ("BCM1_Rueckfahrlicht_Schalter", "Gateway_72", 0)]  # Reverse light from BCM
      checks += [("Motor_14", 10)]  # From J623 Engine control module

    if CP.networkLocation == NWL.fwdCamera:
      # The ACC radar is here on CANBUS.pt
      signals += [("SetSpeed", "ACC_02", 0)]  # ACC set speed
      checks += [("ACC_02", 17)]  # From J428 ACC radar control module
    
    return CANParser(DBC[CP.carFingerprint]['pt'], signals, checks, CANBUS.pt)

  @staticmethod
  def get_pq_can_parser(CP):
    signals = [
      # sig_name, sig_address, default
      ("LH3_BLW", "Lenkhilfe_3", 0),                # Absolute steering angle
      ("LH3_BLWSign", "Lenkhilfe_3", 0),            # Steering angle sign
      ("LH3_LM", "Lenkhilfe_3", 0),                 # Absolute driver torque input
      ("LH3_LMSign", "Lenkhilfe_3", 0),             # Driver torque input sign
      ("LH2_Sta_HCA", "Lenkhilfe_2", 0),            # Steering rack HCA status
      ("Lenkradwinkel_Geschwindigkeit", "Lenkwinkel_1", 0),  # Absolute steering rate
      ("Lenkradwinkel_Geschwindigkeit_S", "Lenkwinkel_1", 0),  # Steering rate sign
      ("Radgeschw__VL_4_1", "Bremse_3", 0),         # ABS wheel speed, front left
      ("Radgeschw__VR_4_1", "Bremse_3", 0),         # ABS wheel speed, front right
      ("Radgeschw__HL_4_1", "Bremse_3", 0),         # ABS wheel speed, rear left
      ("Radgeschw__HR_4_1", "Bremse_3", 0),         # ABS wheel speed, rear right
      ("Giergeschwindigkeit", "Bremse_5", 0),       # Absolute yaw rate
      ("Vorzeichen_der_Giergeschwindigk", "Bremse_5", 0),  # Yaw rate sign
      ("GK1_Fa_Tuerkont", "Gate_Komf_1", 0),     # Door open, driver
      # TODO: locate passenger and rear door states
      ("GK1_Blinker_li", "Gate_Komf_1", 0),         # Left turn signal on
      ("GK1_Blinker_re", "Gate_Komf_1", 0),         # Right turn signal on
      ("Gurtschalter_Fahrer", "Airbag_1", 0),       # Seatbelt status, driver
      ("Gurtschalter_Beifahrer", "Airbag_1", 0),    # Seatbelt status, passenger
      ("Bremstestschalter", "Motor_2", 0),          # Brake pedal pressed (brake light test switch)
      ("Bremslichtschalter", "Motor_2", 0),         # Brakes applied (brake light switch)
      ("Bremsdruck", "Bremse_5", 0),                # Brake pressure applied
      ("Vorzeichen_Bremsdruck", "Bremse_5", 0),     # Brake pressure applied sign (???)
      ("Fahrpedal_Rohsignal", "Motor_3", 0),        # Accelerator pedal value
      ("ESP_Passiv_getastet", "Bremse_1", 0),       # Stability control disabled
      ("MFA_v_Einheit_02", "Einheiten_1", 0),       # MPH vs KMH speed display
      ("Bremsinfo", "Kombi_1", 0),                  # Manual handbrake applied
      ("GRA_Status", "Motor_2", 0),                 # ACC engagement status
      ("Hauptschalter", "GRA_neu", 0),              # ACC button, on/off
      ("Abbrechen", "GRA_neu", 0),                  # ACC button, cancel
      ("Setzen", "GRA_neu", 0),                     # ACC button, set
      ("Lang_Tip_up", "GRA_neu", 0),                # ACC button, increase or accel, long press
      ("Lang_Tip_down", "GRA_neu", 0),              # ACC button, decrease or decel, long press
      ("Kurz_Tip_up", "GRA_neu", 0),                # ACC button, increase or accel, short press
      ("Kurz_Tip_down", "GRA_neu", 0),              # ACC button, decrease or decel, short press
      ("Wiederaufnahme", "GRA_neu", 0),             # ACC button, resume
      ("Zeitlueckenverstellung", "GRA_neu", 0),     # ACC button, time gap adj
    ]

    checks = [
      # sig_address, frequency
      ("Bremse_3", 100),          # From J104 ABS/ESP controller
      ("Lenkhilfe_3", 100),       # From J500 Steering Assist with integrated sensors
      ("Lenkwinkel_1", 100),      # From J500 Steering Assist with integrated sensors
      ("Motor_3", 100),           # From J623 Engine control module
      ("Airbag_1", 50),           # From J234 Airbag control module
      ("Bremse_5", 50),           # From J104 ABS/ESP controller
      ("GRA_neu", 50),            # From J??? steering wheel control buttons
      ("Kombi_1", 50),            # From J285 Instrument cluster
      ("Motor_2", 50),            # From J623 Engine control module
      ("Lenkhilfe_2", 20),        # From J500 Steering Assist with integrated sensors
      ("Gate_Komf_1", 10),     # From J533 CAN gateway
      ("Einheiten_1", 1),         # From J??? cluster or gateway
    ]

    if CP.transmissionType == TRANS.automatic:
      signals += [("Waehlhebelposition__Getriebe_1_", "Getriebe_1", 0)]  # Auto trans gear selector position
      checks += [("Getriebe_1", 100)]  # From J743 Auto transmission control module
    elif CP.transmissionType == TRANS.manual:
      signals += [("Kupplungsschalter", "Motor_1", 0),  # Clutch switch
                  ("GK1_Rueckfahr", "Gate_Komf_1", 0)]  # Reverse light from BCM
      checks += [("Motor_1", 100)]  # From J623 Engine control module

    if CP.networkLocation == NWL.fwdCamera:
      # The ACC radar is here on CANBUS.pt
      signals += [("ACA_V_Wunsch", "ACC_GRA_Anziege", 0)]  # ACC set speed
      checks += [("ACC_GRA_Anziege", 25)]  # From J428 ACC radar control module

    return CANParser(DBC[CP.carFingerprint]['pt'], signals, checks, CANBUS.pt)

  @staticmethod
  def get_mqb_cam_can_parser(CP):
    # TODO: Need to monitor LKAS camera, if present, for TLC/DLC/warning signals for passthru to SWA
    signals = []
    checks = []

    if CP.networkLocation == NWL.gateway:
      # The ACC radar is here on CANBUS.cam
      signals += [("SetSpeed", "ACC_02", 0)]  # ACC set speed
      checks += [("ACC_02", 17)]  # From J428 ACC radar control module

    return CANParser(DBC[CP.carFingerprint]['pt'], signals, checks, CANBUS.cam)

  @staticmethod
  def get_pq_cam_can_parser(CP):
    # TODO: Need to monitor LKAS camera, if present, for TLC/DLC/warning signals for passthru to SWA
    signals = []
    checks = []

    if CP.networkLocation == NWL.gateway:
      # The ACC radar is here on CANBUS.cam
      signals += [("ACA_V_Wunsch", "ACC_GRA_Anziege", 0)]  # ACC set speed
      checks += [("ACC_GRA_Anziege", 25)]  # From J428 ACC radar control module

    return CANParser(DBC[CP.carFingerprint]['pt'], signals, checks, CANBUS.cam)
