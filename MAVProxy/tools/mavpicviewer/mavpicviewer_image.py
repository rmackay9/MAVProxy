#!/usr/bin/env python3

'''
MAV Picture Viewer

Quick and efficient reviewing of images taken from a drone

AP_FLAKE8_CLEAN
'''

from threading import Thread
from queue import Queue
import cv2
import time
import os
import piexif
from mavpicviewer_shared import mavpicviewer_loc, mavpicviewer_pos, mavpicviewer_poi, SetFilenumber, SetFOV, Close, SetPOI, ClearPOI

from MAVProxy.modules.lib import mp_util
from MAVProxy.modules.lib import mp_elevation

if mp_util.has_wxpython:
    from MAVProxy.modules.lib.wx_loader import wx
    from MAVProxy.modules.lib.mp_menu import MPMenuTop
    from MAVProxy.modules.lib.mp_menu import MPMenuItem
    from MAVProxy.modules.lib.mp_menu import MPMenuSubMenu
    from MAVProxy.modules.lib.mp_image import MPImage
    from MAVProxy.modules.mavproxy_map import mp_slipmap
    from MAVProxy.modules.lib import camera_projection
    from MAVProxy.modules.lib.mp_menu import MPMenuCallDirDialog


class mavpicviewer_image:
    """handle camera view image"""

    def __init__(self, filelist, comm_pipe = None):

        # determine if filelist is a string or a list of strings
        self.filenumber = 0
        if type(filelist) is str:
            self.filelist = []
            self.filelist.append(filelist)
        else:
            # use the first item in the list
            self.filelist = filelist

        # record reference to communication queue
        self.comm_pipe = comm_pipe

        # load elevation data
        self.terrain_source = "SRTM3"
        self.terrain_offline = 0
        self.elevation_model = mp_elevation.ElevationModel(self.terrain_source)

        # POIs indexed by filenumber
        self.poi_dict = {}
        self.poi_start_pos = None

        # create image viewer
        self.im = None
        self.update_image()

        # set camera parameters with default FOV
        self.update_camera_settings(36.9)

        # hard-code mount angles
        self.roll = 0
        self.pitch = -90
        self.yaw = 0

        # display map with polygon
        self.sm = None
        self.update_map()

        # exit variable
        self.exit_requested = False

        # create menu
        self.menu = None
        if mp_util.has_wxpython:
            self.menu = MPMenuTop([MPMenuSubMenu('&File',
                                   items=[MPMenuItem('&Save\tCtrl+S'),
                                          MPMenuItem('&Clear POI\tCtrl+C', returnkey='clearpoi'),
                                          MPMenuItem('&Next Image\tCtrl+N', returnkey='nextimage'),
                                          MPMenuItem('&Prev Image\tCtrl+P', returnkey='previmage'),
                                          MPMenuItem('&Quit\tCtrl+Q', 'Quit')])])
            self.im.set_menu(self.menu)

        self.thread = Thread(target=self.mavpicviewer_image_loop, name='mavpicviewer_image_loop')
        self.thread.daemon = False
        self.thread.start()

    # main loop
    def mavpicviewer_image_loop(self):
        """main thread"""
        while not self.exit_requested:
            if self.im is None:
                break
            time.sleep(0.25)
            self.check_events()

            # handle messages from the comm pipe
            if self.comm_pipe is not None:
                # print contents of the queue
                while self.comm_pipe.poll():
                    self.handle_comm_object(self.comm_pipe.recv())

    # handle an object received on the communication pipe
    def handle_comm_object(self, obj):
        """process an object received on the communication pipe"""
        if isinstance(obj, SetFilenumber):
            self.set_filenumber(obj.filenumber, False)
        elif isinstance(obj, SetFOV):
            self.set_fov(obj.fov)
        elif isinstance(obj, Close):
            self.exit_requested = True
            self.im.terminate()
            self.sm.close()

    # send a communication object to the image viewer
    def send_comm_object(self, obj):
        """send a communication object to the image viewer"""
        if self.comm_pipe is not None:
            self.comm_pipe.send(obj)

    # set window title
    def set_title(self, title):
        """set image title"""
        if self.im is None:
            return
        self.im.set_title(title)

    # set FOV
    def set_fov(self, fov_deg):
        """set image title"""
        self.update_camera_settings(fov_deg)
        self.update_map()

    # process window events
    def check_events(self):
        """check for image events"""
        if self.im is None:
            return
        if not self.im.is_alive():
            self.im = None
            return
        for event in self.im.events():
            if isinstance(event, MPMenuItem):
                if event.returnkey == "fitWindow":
                    print("fitting to window")
                    self.im.fit_to_window()
                elif event.returnkey == "fullSize":
                    print("full size")
                    self.im.full_size()
                elif event.returnkey == "clearpoi":
                    self.cmd_clear_poi()
                elif event.returnkey == "nextimage":
                    self.cmd_nextimage()
                elif event.returnkey == "previmage":
                    self.cmd_previmage()
                continue
            if event.ClassName == "wxMouseEvent":
                if event.X is not None and event.Y is not None:
                    if event.leftIsDown:
                        self.poi_capture_start(event.X, event.Y)
                    else:
                        self.poi_capture_done(event.X, event.Y)
                else:
                    # if no X,Y coordinates then probably outside of window
                    self.poi_cancel()
            if event.ClassName == "wxKeyEvent":
                keycode = event.KeyCode
                if keycode == wx.WXK_LEFT:
                    self.cmd_previmage()
                elif keycode == wx.WXK_RIGHT:
                    self.cmd_nextimage()

    # start capturing POI rectangle around part of image
    def poi_capture_start(self, X, Y):
        """handle user request to start capturing box around part of image"""
        if self.poi_start_pos is None:
            self.poi_start_pos = mavpicviewer_pos(X, Y)

    # complete capturing box around part of image
    def poi_capture_done(self, X, Y):
        """handle user request to complete capturing box around part of image"""
        if self.poi_start_pos is not None:
            # exit if mouse has not moved a sufficient distance
            if abs(X - self.poi_start_pos.X) <= 5 or abs(Y - self.poi_start_pos.Y) <= 5:
                self.poi_start_pos = None
                return
            # calculate location of each corner
            lat1, lon1, alt1 = self.get_latlonalt(self.poi_start_pos.X, self.poi_start_pos.Y)
            lat2, lon2, alt2 = self.get_latlonalt(X, Y)
            if lat1 is None or lat2 is None:
                print("picviewer: POI capture failed")
                return
            # add POI object to dictionary
            poi = mavpicviewer_poi(self.poi_start_pos, mavpicviewer_pos(X, Y),
                                mavpicviewer_loc(lat1, lon1, alt1),
                                mavpicviewer_loc(lat2, lon2, alt2))
            self.poi_dict[self.filenumber] = poi
            self.send_comm_object(SetPOI(self.filenumber, poi))
            self.poi_start_pos = None
            # update image
            self.update_image()
            # add retangle to map
            self.add_rectangle_to_map(self.filename, lat1, lon1, lat2, lon2)

    # camcel capturing box around part of image.  should be called if mouse leaves window, next image is loaded, etc
    def poi_cancel(self):
        self.poi_start_pos = None

    # clear poi from current image
    def cmd_clear_poi(self):
        self.poi_cancel()
        if self.filenumber in self.poi_dict.keys():
            self.poi_dict.pop(self.filenumber)
            self.update_image()
            self.remove_rectangle_from_map(self.filename)
            self.send_comm_object(ClearPOI(self.filenumber))

    # update current image to next image
    def cmd_nextimage(self):
        self.set_filenumber(self.filenumber + 1)

    # update current image to previous image
    def cmd_previmage(self):
        self.set_filenumber(self.filenumber - 1)

    # image select callback
    def set_filenumber(self, filenumber, notify_mosaic=True):
        if filenumber < 0:
            print("picviewer: already at first image")
            return
        if filenumber >= len(self.filelist):
            print("picviewer: already at last image %d" % self.filenumber)
            return
        self.filenumber = filenumber
        self.update_image()
        self.update_map()
        if notify_mosaic:
            self.send_comm_object(SetFilenumber(self.filenumber))

    # update the displayed image
    # should be called if filenumber is changed
    def update_image(self):
        # update filename
        self.filename = self.filelist[self.filenumber]
        base_filename = os.path.basename(self.filename)

        # create image viewer if required
        if self.im is None:
            print("picviewer: creating image viewer")
            self.im = MPImage(title=base_filename,
                              mouse_events=True,
                              mouse_movement_events=True,
                              key_events=True,
                              can_drag=False,
                              can_zoom=True,
                              auto_size=False,
                              auto_fit=True)

        # check if image viewer was created
        if self.im is None:
            print("picviewer: failed to create image viewer")
            return

        # set title to filename
        title_str = base_filename + " (" + str(self.filenumber+1) + " of " + str(len(self.filelist)) + ")"
        self.set_title(title_str)

        # load image from file
        image = cv2.imread(self.filename)

        # add POI rectangles to image
        if self.filenumber in self.poi_dict.keys():
            poi = self.poi_dict.get(self.filenumber)
            cv2.rectangle(image, (poi.pos1.X, poi.pos1.Y), (poi.pos2.X, poi.pos2.Y), (255, 0, 0), 2)

        # update image and colormap
        self.im.set_image(image)
        self.im.set_colormap("None")

        # load exif data
        self.lat, self.lon, self.alt_amsl, self.terr_alt = self.exif_location(self.filename)

    # update camera settings
    def update_camera_settings(self, FOV):
        if self.im is None:
            print("picviewer: failed to update camera settings because image not set")
            return
        # set camera parameters
        self.cam1_params = camera_projection.CameraParams(xresolution=self.im.width, yresolution=self.im.height, FOV=FOV)
        self.cam1_projection = camera_projection.CameraProjection(self.cam1_params, self.elevation_model, self.terrain_source)

    # update the displayed map with polygon
    # should be called if filenumber is changed
    def update_map(self):
        # create and display map
        if self.sm is None:
            self.sm = mp_slipmap.MPSlipMap(lat=self.lat, lon=self.lon, elevation=self.terrain_source)
        if self.sm is None:
            print("picviewer: failed to create map")
            return

        # update map center
        self.sm.set_center(self.lat, self.lon)

        projection1 = self.cam1_projection.get_projection(self.lat, self.lon, self.alt_amsl, self.roll, self.pitch, self.yaw)
        if projection1 is not None and self.sm is not None:
            self.sm.add_object(mp_slipmap.SlipPolygon('projection1', projection1, layer=1, linewidth=2, colour=(0, 255, 0)))
        else:
            print("picviewer: failed to add projection to map")

    # add a rectangle specified by two locations to the map
    def add_rectangle_to_map(self, name, lat1, lon1, lat2, lon2):
        if self.sm is not None:
            rect = [(lat1, lon1), (lat1, lon2), (lat2, lon2), (lat2, lon1), (lat1, lon1)]
            self.sm.add_object(mp_slipmap.SlipPolygon(name, rect, layer=1, linewidth=2, colour=(255, 0, 0)))

    # remove a rectangle from the map
    def remove_rectangle_from_map(self, name):
        if self.sm is not None:
            self.sm.remove_object(name)

    # get location (e.g lat, lon, alt, terr_alt) from image's exif tags
    def exif_location(self, filename):
        """get latitude, longitude, altitude and terrain_alt from exif tags"""

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

    def get_latlonalt(self, pixel_x, pixel_y):
        '''
        get ground lat/lon given vehicle orientation, camera orientation and slant range
        pixel_x and pixel_y are in image pixel coordinates with 0,0 at the top left
        '''
        if self.cam1_params is None:
            print("picviewer: failed to calc lat,lon because camera params not set")
            return None

        return self.cam1_projection.get_latlonalt_for_pixel(int(pixel_x), int(pixel_y),
                                                            self.lat, self.lon, self.alt_amsl,
                                                            self.roll, self.pitch, self.yaw)
