'''
Picture Viewer Module
Randy Mackay, Aug 2024

This module allows easier viewing of images taken from a drone camera

AP_FLAKE8_CLEAN
'''

from MAVProxy.modules.lib import mp_module
from MAVProxy.modules.lib import mp_settings
from MAVProxy.modules.lib.mp_settings import MPSetting
from MAVProxy.modules.lib import mp_util
from MAVProxy.modules.mavproxy_picviewer import picviewer_window
from MAVProxy.modules.lib import camera_projection
from pymavlink import mavutil
from pymavlink import DFReader
from pymavlink.rotmat import Matrix3
from pymavlink.rotmat import Vector3
import math
from math import radians, degrees
from threading import Thread
import traceback
from pathlib import Path

import socket, time, os, struct

if mp_util.has_wxpython:
    from MAVProxy.modules.lib.mp_menu import MPMenuCallTextDialog
    from MAVProxy.modules.lib.mp_menu import MPMenuCallFileDialog
    from MAVProxy.modules.lib.mp_menu import MPMenuCallDirDialog
    from MAVProxy.modules.lib.mp_menu import MPMenuItem
    from MAVProxy.modules.lib.mp_menu import MPMenuSubMenu
    from MAVProxy.modules.lib.mp_image import MPImage
    from MAVProxy.modules.mavproxy_map import mp_slipmap

from MAVProxy.modules.mavproxy_SIYI.camera_view import CameraView

class picviewer(mp_module.MPModule):

    def __init__(self, mpstate):

        # call parent class
        super(picviewer, self).__init__(mpstate, "picviewer", "picture viewer")

        # register module and commands
        self.add_command('picviewer', self.cmd_picviewer, "picviewer module", ["openfolder", "openfile"])

        # keep reference to mpstate
        self.mpstate = mpstate

        # settings for this module
        self.picviewer_settings = mp_settings.MPSettings([('fov', float, 62.0),
                                                          MPSetting('thresh_climit', int, 50, range=(10,50))
                                                         ])
        self.menu = None
        if mp_util.has_wxpython:
            self.menu = MPMenuSubMenu('PicViewer',
                                      items=[MPMenuItem('Open Folder', 'OpenFolder', '# picviewer openfolder ',
                                                        handler=MPMenuCallDirDialog(title='Select Folder')),
                                             MPMenuItem('Open File', 'OpenFile', '# picviewer openfile ',
                                                        handler=MPMenuCallFileDialog(flags=('open',), title='Open File', wildcard='*.*')),
                                            ])

            console = self.module('console')
            if console is not None:
                console.add_menu(self.menu)

        # reduce startup time during dev by opening a file
        #self.cmd_openfile("/home/rmackay9/GitHub/r9-MAVProxy/XACT0001.JPG")
        self.cmd_openfolder("/home/rmackay9/GitHub/r9-MAVProxy")

    # show help on command line options
    def usage(self):
        return "Usage: picviewer <openfolder|openfile>"

    # command line handler
    def cmd_picviewer(self, args):
        '''picviewer'''
        len_args = len(args)
        if len_args == 0:
            print(self.usage())
            return
        if args[0] == 'openfolder':
            if len_args != 2:
                print("Usage: picviewer openfolder <folderpath>")
                return
            self.cmd_openfolder(args[1])
        elif args[0] == 'openfile':
            if len_args != 2:
                print("Usage: picviewer openfile <filepath>")
                return
            self.cmd_openfile(args[1])

    # display dialog to open a folder
    def cmd_openfolder(self, folderpath):
        file_list = self.file_list(folderpath, ['jpg', 'jpeg'])
        if file_list is None or not file_list:
            print("picviewer: no files found")
            return
        self.picviewer_window = picviewer_window.picviewer_window(self.mpstate, file_list)

    # open picture viewer to display a single file
    def cmd_openfile(self, filepath):
        # check file exists
        if not Path(filepath).exists():
            print("picviewer: %s not found" % filepath)
            return
        filelist = []
        filelist.append(filepath)
        self.picviewer_window = picviewer_window.picviewer_window(self.mpstate, filelist)

    # return an array of files for a given directory and extension
    def file_list(self, directory, extensions):
        '''return file list for a directory'''
        flist = []
        for filename in os.listdir(directory):
            extension = filename.split('.')[-1]
            if extension.lower() in extensions:
                flist.append(os.path.join(directory, filename))
        sorted_list = sorted(flist, key=str.lower)
        return sorted_list

def init(mpstate):
    '''initialise module'''
    return picviewer(mpstate)
