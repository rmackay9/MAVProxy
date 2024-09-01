#!/usr/bin/env python3

'''
MAV Picture Viewer

Quick and efficient reviewing of images taken from a drone
'''

from argparse import ArgumentParser
from pathlib import Path
import os

import picviewer_window

prefix_str = "mavpicviewer: "


class mavpicviewer():

    # constructor
    def __init__(self):
        self.picviewer_window = None

    # display dialog to open a folder
    def cmd_openfolder(self, folderpath):
        file_list = self.file_list(folderpath, ['jpg', 'jpeg'])
        if file_list is None or not file_list:
            print("picviewer: no files found")
            return
        self.picviewer_window = picviewer_window.picviewer_window(file_list)

    # open picture viewer to display a single file
    def cmd_openfile(self, filepath):
        # check file exists
        if not Path(filepath).exists():
            print("picviewer: %s not found" % filepath)
            return
        filelist = []
        filelist.append(filepath)
        self.picviewer_window = picviewer_window.picviewer_window(filelist)

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


# main function
def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("filepath", default=".", help="filename or directory holding images")
    args = parser.parse_args()

    # check destination directory exists
    if not os.path.exists(args.filepath):
        exit(prefix_str + "invalid destination directory")

    # check if file or directory
    if os.path.isfile(args.filepath):
        picviewer = mavpicviewer()
        picviewer.cmd_openfile(args.filepath)
    else:
        picviewer = mavpicviewer()
        picviewer.cmd_openfolder(args.filepath)


# main
if __name__ == "__main__":
    main()
