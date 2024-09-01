#!/usr/bin/env python3

'''
MAV Picture Viewer

Quick and efficient reviewing of images taken from a drone

AP_FLAKE8_CLEAN
'''

from threading import Thread
import cv2
import time
import os
import piexif
from mavpicviewer_shared import mavpicviewer_loc, mavpicviewer_pos, mavpicviewer_poi

from MAVProxy.modules.lib import mp_util
from MAVProxy.modules.lib import mp_elevation

if mp_util.has_wxpython:
    from MAVProxy.modules.lib.wx_loader import wx
    from MAVProxy.modules.mavproxy_map import mp_slipmap
    from MAVProxy.modules.lib import camera_projection


class mavpicviewer_map(mp_slipmap.MPSlipMap):
    pass
    # call parent init
    #def __init__(self):
    #    print("mavpicviewer_map init")



