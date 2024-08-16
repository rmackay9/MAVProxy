#!/usr/bin/env python3

'''
Picture Viewer Window

Displays a window for users to review a collection of images quickly

AP_FLAKE8_CLEAN
'''

from threading import Thread
from math import ceil
import cv2
import time, sys
import piexif
import os

from MAVProxy.modules.lib import mp_util

if mp_util.has_wxpython:
    from MAVProxy.modules.lib.wx_loader import wx
    from MAVProxy.modules.lib.mp_menu import MPMenuTop
    from MAVProxy.modules.lib.mp_menu import MPMenuItem
    from MAVProxy.modules.lib.mp_menu import MPMenuSubMenu
    from MAVProxy.modules.lib.mp_image import MPImage
    from MAVProxy.modules.lib.mp_menu import MPMenuCallDirDialog

import numpy as np

class mosaic_window:
    """displays a mosaic of images"""

    def __init__(self, mpstate, filelist):

        # keep reference to mpstate
        self.mpstate = mpstate

        # determine if filelist is a string or a list of strings
        self.filenumber = 0
        if type(filelist) is str:
            self.filelist = []
            self.filelist.append(filelist)
        else:
            # use the first item in the list
            self.filelist = filelist

        # hardcoded thumbnail image size and number of columns
        self.thumb_size = 100
        self.thumb_columns = 5
        self.thumb_rows = ceil(len(filelist) / self.thumb_columns)

        # create image viewer
        self.im = None
        self.update_image()

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

        self.thread = Thread(target=self.mosaic_window_loop, name='mosaic_window_loop')
        self.thread.daemon = False
        self.thread.start()

    # main loop
    def mosaic_window_loop(self):
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
            #print(event.ClassName)
            if isinstance(event, MPMenuItem):
                if event.returnkey == "openfolder":
                    self.cmd_openfolder()
                elif event.returnkey == "fitWindow":
                    print("fitting to window")
                    self.im.fit_to_window()
                elif event.returnkey == "fullSize":
                    print("full size")
                    self.im.full_size()
                elif event.returnkey == "nextimage":
                    self.cmd_nextimage()
                elif event.returnkey == "previmage":
                    self.cmd_previmage()
                else:
                    debug_str = "event: %s" % event
                    self.set_title(debug_str)
                continue
            if event.ClassName == "wxMouseEvent":
                if event.X is not None and event.Y is not None:
                    print("mosaic pixel x:%f y:%f" % (event.X, event.Y))

    # display dialog to open a folder
    def cmd_openfolder(self):
        print("I will open a folder")

    # display dialog to open a file
    def cmd_openfile(self):
        print("I will open a file")

    # update current image to next image
    def cmd_nextimage(self):
        if self.filenumber >= len(self.filelist) -1 :
            print("picviewer: already at last image %d" % self.filenumber)
            return
        self.filenumber = self.filenumber + 1
        self.update_image()

    # update current image to previous image
    def cmd_previmage(self):
        if self.filenumber <= 0:
            print("picviewer: already at first image")
            return
        self.filenumber = self.filenumber - 1
        self.update_image()

    # update the mosaic of images
    # should be called if filenumber is changed
    def update_image(self):
        # update filename
        self.filename = self.filelist[self.filenumber]
        base_filename = os.path.basename(self.filename)

        # create image viewer if required
        if self.im is None:
            self.im = MPImage(title=base_filename,
                              mouse_events=True,
                              mouse_movement_events=True,
                              key_events=True,
                              can_drag=True,
                              can_zoom=False,
                              auto_size=False,
                              auto_fit=False)

        # check if image viewer was created
        if self.im is None:
            print("picviewer: failed to create image viewer")
            return

        # set title to filename
        self.set_title("Mosaic " + base_filename)

        # create blank image
        temp_image = cv2.imread(self.filename)
        h, w, c = temp_image.shape
        print("image shape: %d %d %d" % (h, w, c))
        mosaic_image = 255 * np.ones(shape=(self.thumb_rows * self.thumb_size, self.thumb_columns * self.thumb_size, c), dtype=np.uint8)

        # iterate through images and add thumbnails to mosaic
        row = 0
        col = 0
        for i in range(len(self.filelist)):
            image_filename = self.filelist[i]
            image = cv2.imread(image_filename)
            image_small = cv2.resize(image, (self.thumb_size, self.thumb_size), interpolation=cv2.INTER_AREA)
            self.overlay_image(mosaic_image, image_small, col * self.thumb_size, row * self.thumb_size)
            col = col + 1
            if col >= self.thumb_columns:
                col = 0
                row = row + 1

        # update image and colormap
        self.im.set_image(mosaic_image)
        self.im.set_colormap("None")

    def overlay_image(self, img, img2, x, y):
        '''overlay a 2nd image on a first image, at position x,y on the first image'''
        (img_width,img_height) = self.image_shape(img2)
        img[y:y+img_height, x:x+img_width] = img2

    def image_shape(self, img):
        '''return (w,h) of an image, coping with different image formats'''
        height, width = img.shape[:2]
        return (width, height)