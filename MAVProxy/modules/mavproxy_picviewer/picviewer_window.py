#!/usr/bin/env python3

'''
Picture Viewer Window

Displays a window for users to review a collection of images quickly

AP_FLAKE8_CLEAN
'''

from threading import Thread
import cv2
import time, sys
import piexif

from MAVProxy.modules.lib import mp_util
from MAVProxy.modules.lib import mp_elevation

if mp_util.has_wxpython:
    from MAVProxy.modules.lib.wx_loader import wx
    from MAVProxy.modules.lib.mp_menu import MPMenuTop
    from MAVProxy.modules.lib.mp_menu import MPMenuItem
    from MAVProxy.modules.lib.mp_menu import MPMenuSubMenu
    from MAVProxy.modules.lib.mp_image import MPImage
    from MAVProxy.modules.lib.mp_image import MPImageTrackPos
    from MAVProxy.modules.lib.mp_image import MPImageFrameCounter
    from MAVProxy.modules.mavproxy_map import mp_slipmap
    from MAVProxy.modules.lib.mp_menu import MPMenuCallFileDialog
    from MAVProxy.modules.lib.mp_menu import MPMenuCallDirDialog

import numpy as np

class picviewer_window:
    """handle camera view image"""

    def __init__(self, mpstate, filename):

        # keep reference to mpstate and filename
        self.mpstate = mpstate
        self.filename = filename

        # create image viewer
        self.im = MPImage(
            title="Picture Viewer",
            mouse_events=True,
            mouse_movement_events=True,
            key_events=True,
            can_drag=False,
            can_zoom=True,
            auto_size=False,
            auto_fit=True,
        )
        self.im.set_colormap("None")
        self.im.set_image(cv2.imread(self.filename))
        self.set_title(self.filename)

        # load elevation data
        self.elevation_model = mp_elevation.ElevationModel()

        # load exif data
        lat, lon, alt, terr_alt = self.exif_location(self.filename)
        #exif_dic = piexif.load(self.filename)
        #print("EXIF data:")
        #for exif_key, exif_value in exif_dic.items():
        #    #print(exif_key, exif_value)
        #    print(exif_key)
        #print("-----------------")
        print("Image Lat:%f lon:%f alt:%f talt:%f" % (lat, lon, alt, terr_alt))

        # create menu
        self.menu = None
        if mp_util.has_wxpython:
            self.menu = MPMenuTop([MPMenuSubMenu('&File',
                                    items=[MPMenuItem(name='&Open\tCtrl+O', returnkey='openfolder',
                                                                            handler=MPMenuCallDirDialog(title='Open Folder')),
                                                                            #handler=MPMenuCallFileDialog(flags=('open','multiple',),
                                                                            #                             title='Open Folder',
                                                                            #                             wildcard='*.*')),
                                           MPMenuItem('&Save\tCtrl+S'),
                                           MPMenuItem('Close', 'Close'),
                                           MPMenuItem('&Quit\tCtrl+Q', 'Quit')])])
            self.im.set_menu(self.menu)

            popup = self.im.get_popup_menu()
            popup.add_to_submenu(["Mode"], MPMenuItem("ClickTrack", returnkey="Mode:ClickTrack"))
            popup.add_to_submenu(["Mode"], MPMenuItem("Flag", returnkey="Mode:Flag"))

        self.thread = Thread(target=self.picviewer_window_loop, name='picviewer_window_loop')
        self.thread.daemon = False
        self.thread.start()

    # main loop
    def picviewer_window_loop(self):
        """main thread"""
        while True:
            if self.im is None:
                break
            time.sleep(0.25)
            self.check_events()

    # set window title
    def set_title(self, title):
        """set image title"""
        if self.im is None:
            return
        self.im.set_title(title)

    # process window events
    def check_events(self):
        """check for image events"""
        if self.im is None:
            return
        if not self.im.is_alive():
            self.im = None
            return
        for event in self.im.events():
            # print event
            #print(event)
            if isinstance(event, MPMenuItem):
                if event.returnkey == "openfolder":
                    self.cmd_openfolder()
                elif event.returnkey == "fitWindow":
                    print("fitting to window")
                    self.im.fit_to_window()
                elif event.returnkey == "fullSize":
                    print("full size")
                    self.im.full_size()
                else:
                    debug_str = "event: %s" % event
                    self.set_title(debug_str)
                continue
            if event.ClassName == "wxMouseEvent":
                if event.pixel is not None:
                    self.update_title("hello")

    # display dialog to open a folder
    def cmd_openfolder(self):
        print("I will open a folder")

    # display dialog to open a file
    def cmd_openfile(self):
        print("I will open a file")

    # get location (e.g lat, lon, alt, terr_alt) from image's exif tags
    def exif_location(self, filename):
        """get latitude, longitude, altitude and terrain_alt from exif tags"""
        import piexif
        global _last_position
        
        exif_dict = piexif.load(filename)

        if piexif.GPSIFD.GPSLatitudeRef in exif_dict["GPS"]:
            lat_ns = exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef]
            lat = self.dms_to_decimal(exif_dict["GPS"][piexif.GPSIFD.GPSLatitude][0],
                                      exif_dict["GPS"][piexif.GPSIFD.GPSLatitude][1],
                                      exif_dict["GPS"][piexif.GPSIFD.GPSLatitude][2],
                                      lat_ns)
            lon_ew = exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef]
            lon = self.dms_to_decimal(exif_dict["GPS"][piexif.GPSIFD.GPSLongitude][0],
                                      exif_dict["GPS"][piexif.GPSIFD.GPSLongitude][1],
                                      exif_dict["GPS"][piexif.GPSIFD.GPSLongitude][2],
                                      lon_ew)
            alt = float(exif_dict["GPS"][piexif.GPSIFD.GPSAltitude][0])/float(exif_dict["GPS"][piexif.GPSIFD.GPSAltitude][1])
            terr_alt = self.elevation_model.GetElevation(lat, lon)
            if terr_alt is None:
                print("WARNING: failed terrain lookup for %f %f" % (lat, lon))
                terr_alt = 0
        else:
            lat = 0
            lon = 0
            alt = 0
            terr_alt = 0

        return lat, lon, alt, terr_alt

    def dms_to_decimal(self, degrees, minutes, seconds, sign=b' '):
        """Convert degrees, minutes, seconds into decimal degrees.

        >>> dms_to_decimal((10, 1), (10, 1), (10, 1))
        10.169444444444444
        >>> dms_to_decimal((8, 1), (9, 1), (10, 1), 'S')
        -8.152777777777779
        """
        return (-1 if sign in b'SWsw' else 1) * (
            float(degrees[0])/float(degrees[1])        +
            float(minutes[0])/float(minutes[1]) / 60.0   +
            float(seconds[0])/float(seconds[1]) / 3600.0
        )