#!/usr/bin/bash
/usr/bin/sh /data/openpilot/scripts/toyota_dsu+_mode.sh
if [ -f "/sdcard/dp_patcher.py" ]; then
    /data/data/com.termux/files/usr/bin/python /sdcard/dp_patcher.py
fi
getprop persist.sys.locale | tr -d '\n' > /data/params/d/DragonLocale
chmod +x scripts/*.sh
/usr/bin/sh /data/openpilot/dragonpilot/cjk-fonts/installer.sh &
export PASSIVE="0"
exec ./launch_chffrplus.sh

