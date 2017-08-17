#!/usr/bin/env python
''' This file is intended to be a helper for running whitebox-tools plugins from a Python script.
See whitebox_example.py for an example of how to use it.
'''
from __future__ import print_function
import os
from os import path
import pipes
import sys
from sys import platform
from subprocess import CalledProcessError, Popen, PIPE, STDOUT

WHITEBOX_VERBOSE = bool(int(os.environ.get('WHITEBOX_VERBOSE', '1')))

BUILD_PATH_PARTS = ('share', 'whitebox_tools',
                    'release', 'whitebox_tools',)

EXE_PATH = None
CONDA_PREFIX = os.environ.get('CONDA_PREFIX')
WHITEBOX_TOOLS_BUILD = os.environ.get('WHITEBOX_TOOLS_BUILD')
if CONDA_PREFIX and os.path.exists(CONDA_PREFIX):
    path_guess = os.path.join(CONDA_PREFIX, *BUILD_PATH_PARTS)
    if platform == 'win32':
        path_guess += '.exe'
    if os.path.exists(path_guess):
        EXE_PATH = path_guess
if EXE_PATH is None or WHITEBOX_TOOLS_BUILD:
    if WHITEBOX_TOOLS_BUILD and os.path.exists(WHITEBOX_TOOLS_BUILD):
        for idx in range(len(BUILD_PATH_PARTS)):
            pg = os.path.join(WHITEBOX_TOOLS_BUILD, *BUILD_PATH_PARTS[idx:])
            if platform == 'win32':
                pg += '.exe'
            if os.path.exists(pg):
                EXE_PATH = pg


def default_callback(value):
    ''' A simple default callback that outputs using the print function.
    '''
    print(value)


class WhiteboxTools(object):
    ''' An object for interfacing with the whitebox - tools executable.
    '''
    # exe_path = path.dirname(path.abspath(__file__))
    # wd = ""
    # verbose = True

    def __init__(self, exe_path=None):
        self.set_whitebox_dir(exe_path)
        self.wkdir = ""
        self.verbose = WHITEBOX_VERBOSE
        self.cancel_op = False

    def set_whitebox_dir(self, exe_path=None):
        ''' Sets the directory to the whitebox - tools executable file.
        '''
        exe_paths = (EXE_PATH, exe_path,)
        found_it = False
        for exe_path in exe_paths:
            if exe_path and os.path.exists(exe_path):
                if exe_path.endswith(('whitebox_tools', 'whitebox_tools.exe')):
                    found_it = True
                    break
        if not found_it:
            raise ValueError('Define WHITEBOX_TOOLS_BUILD '
                             'environment variable {}'.format(exe_paths))
        self.exe_path = os.path.dirname(os.path.abspath(exe_path))
        self.exe_name = exe_path

    def set_working_dir(self, path_str):
        ''' Sets the working directory.
        '''
        self.wkdir = path_str

    def set_verbose_mode(self, val=True):
        ''' Sets verbose mode(i.e. whether a running tool outputs).
        '''
        self.verbose = val

    def _run_process(self, args, **kwargs):
        callback = kwargs.get('callback', default_callback)
        if kwargs.get('verbose') or self.verbose:
            pretty_print = ' '.join(pipes.quote(arg) for arg in args)
            print('Running: {}'.format(pretty_print))
        proc = Popen(args, shell=False, stdout=PIPE,
                         stderr=STDOUT, bufsize=1,
                         universal_newlines=True,
                         cwd=self.exe_path)
        lines = []
        silent = kwargs.get('silent')
        ret_code = 0
        while True:
            line = proc.stdout.readline()
            sys.stdout.flush()
            if line != '':
                if not self.cancel_op and not silent:
                    callback(line.strip())
                else:
                    self.cancel_op = False
                    proc.terminate()
                    ret_code = 2
            else:
                break
            lines.append(line)
        ret_code = ret_code or proc.poll()
        return ret_code, lines

    def run_tool(self, tool_name, args,
                 callback=default_callback,
                 verbose=WHITEBOX_VERBOSE):
        ''' Runs a tool and specifies tool arguments.
        Returns 0 if completes without error.
        Returns 1 if error encountered (details are sent to callback).
        Returns 2 if process is cancelled by user.
        '''
        try:
            args2 = []
            args2.append(self.exe_name)
            args2.append("--run=\"{}\"".format(tool_name))

            if not any(a.startswith('--wd=') for a in set(args2 + list(args))):
                wkdir = self.wkdir or os.path.abspath(os.curdir)
                args2.append("--wd=\"{}\"".format(wkdir))

            for arg in args:
                args2.append(arg)

            # args_str = args_str[:-1]
            # a.append("--args=\"{}\"".format(args_str))

            if self.verbose or verbose:
                args2.append("-v")
            return self._run_process(args2, callback=callback, silent=False)[0] or 0
        except (OSError, ValueError, CalledProcessError) as err:
            callback(str(err))
            return 1

    def help(self):
        ''' Retrieve the help description for whitebox - tools.
        '''
        try:
            args = []
            args.append(self.exe_name)
            args.append("-h")
            return self._run_process(args)[1]
        except (OSError, ValueError, CalledProcessError) as err:
            return err

    def license(self):
        ''' Retrieves the license information for whitebox - tools.
        '''
        try:
            args = []
            args.append(self.exe_name)
            args.append("--license")
            return self._run_process(args)[1]
        except (OSError, ValueError, CalledProcessError) as err:
            return err

    def version(self):
        ''' Retrieves the version information for whitebox - tools.
        '''
        try:
            args = []
            args.append(self.exe_name)
            args.append("--version")

            return self._run_process(args)[1]
        except (OSError, ValueError, CalledProcessError) as err:
            return err

    def tool_help(self, tool_name, silent=False):
        ''' Retrieve the help description for a specific tool.
        '''
        try:
            args = []
            args.append(self.exe_name)
            args.append("--toolhelp={}".format(tool_name))
            return self._run_process(args, silent=silent)[1]
        except (OSError, ValueError, CalledProcessError) as err:
            return err

    def list_tools(self):
        ''' Lists all available tools in whitebox - tools.
        '''
        try:
            args = []
            args.append(self.exe_name)
            args.append("--listtools")

            proc = Popen(args, shell=False, stdout=PIPE,
                         stderr=STDOUT, bufsize=1, universal_newlines=True)
            return self._run_process(args)[1]
        except (OSError, ValueError, CalledProcessError) as err:
            return err
