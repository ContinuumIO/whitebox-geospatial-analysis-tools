#!/usr/bin/env python
''' This module provides examples of how to call the whitebox_tool script and the
whitebox-tools geospatial analysis library using Python code.
'''
from __future__ import print_function
from functools import partial
import os
import sys
from whitebox_cli import make_wbt


def main(wbt=None, run_func=None):
    ''' main function
    '''
    try:
        wbt = wbt or make_wbt()
        # Prints the whitebox-tools help...a listing of available commands
        print(wbt.help())

        # Prints the whitebox-tools license
        print(wbt.license())

        # Prints the whitebox-tools version
        print("Version information: {}".format(wbt.version()))

        # List all available tools in whitebox-tools
        print(wbt.list_tools())

        # print(wbt.tool_help("dev_from_mean_elev"))
        print(wbt.tool_help("elev_percentile"))

        # Sets verbose mode (True or False). Most tools will suppress output (e.g. updating
        # progress) when verbose mode is False. The default is True
        # wbt.set_verbose_mode(False)

        # needed to specify complete file names (with paths) to tools that you run.
        wbt.set_working_dir(os.path.dirname(
            os.path.abspath(__file__)) + "/testdata/")

        name = "elev_percentile"
        args = ["--input=\"DEM.dep\"",
                "--output=\"DEV_101.dep\"",
                "--filter=101"]

        # Run the tool and check the return value
        if not run_func:
            if wbt.run_tool(name, args, callback) != 0:
                raise ValueError("ERROR running {}".format(name))
        else:
            if run_func(args, callback) != 0:
                raise ValueError("ERROR running {}".format(name))

    except:
        print("Unexpected error:", sys.exc_info()[0])
        raise



if __name__ == '__main__':
    main()
