from functools import partial
from itertools import chain
import argparse
import json
import os
import re
import sys
try:
    unicode
except:
    unicode = str

from whitebox_tools.whitebox_base import WhiteboxTools
from whitebox_tools.xarray_io import xarray_whitebox_io

TOOL_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'data',
                              'tool_data.json')

tools = ['Aspect',
 'AverageOverlay',
 'BufferRaster',
 'Clump',
 'D8FlowAccumulation',
 'D8Pointer',
 'DInfFlowAccumulation',
 'DevFromMeanElev',
 'DiffFromMeanElev',
 'ElevPercentile',
 'EuclideanAllocation',
 'EuclideanDistance',
 'FD8FlowAccumulation',
 'FillMissingData',
 'FlightlineOverlap',
 'HighestPosition',
 'Hillshade',
 'LidarElevationSlice',
 'LidarGroundPointFilter',
 'LidarHillshade',
 'LidarInfo',
 'LidarJoin',
 'LidarTophatTransform',
 'LowestPosition',
 'MaxAbsoluteOverlay',
 'MaxOverlay',
 'MinAbsoluteOverlay',
 'MinOverlay',
 'NormalVectors',
 'NumDownslopeNeighbours',
 'NumInflowingNeighbours',
 'NumUpslopeNeighbours',
 'PercentElevRange',
 'PlanCurvature',
 'ProfileCurvature',
 'Quantiles',
 'RelativeAspect',
 'RelativeTopographicPosition',
 'RemoveOffTerrainObjects',
 'RuggednessIndex',
 'Slope',
 'TangentialCurvature',
 'TotalCurvature',
 'Watershed',
 'WeightedSum',
 'ZScores']

def callback(out_str, silent=False):
    ''' Create a custom callback to process the text coming out of the tool.
    If a callback is not provided, it will simply print the output stream.
    A custom callback allows for processing of the output stream.
    '''
    try:
        if not hasattr(callback, 'prev_line_progress'):
            callback.prev_line_progress = False
        if "%" in out_str:
            str_array = out_str.split(" ")
            label = out_str.replace(str_array[len(str_array) - 1], "").strip()
            progress = int(
                str_array[len(str_array) - 1].replace("%", "").strip())
            if callback.prev_line_progress:
                if not silent:
                    print('{0} {1}%'.format(label, progress), end="\r")
            else:
                callback.prev_line_progress = True
                if not silent:
                    print(out_str)
        elif "error" in out_str.lower():
            if not silent:
                print("ERROR: {}".format(out_str))
            callback.prev_line_progress = False
        elif "elapsed time (excluding i/o):" in out_str.lower():
            elapsed_time = ''.join(
                ele for ele in out_str if ele.isdigit() or ele == '.')
            units = out_str.lower().replace("elapsed time (excluding i/o):",
                                            "").replace(elapsed_time, "").strip()
            if not silent:
                print("Elapsed time: {0}{1}".format(elapsed_time, units))
            callback.prev_line_progress = False
        else:
            if callback.prev_line_progress:
                if not silent:
                    print('\n{0}'.format(out_str))
                callback.prev_line_progress = False
            elif not silent:
                print(out_str)

    except:
        print(out_str)


def convert_help_extract_params(tool, wbt, to_parser=True, silent=False):
    tool = tool.strip()
    help_str = "\n".join(wbt.tool_help(tool, silent=silent))
    if not silent:
        print('help_str', help_str)
    pattern = './whitebox_tools -r=' + tool
    tool_name = 'whitebox-' + tool
    help_str = help_str.replace(pattern, tool_name)
    help_lines = []
    args = {}
    in_params = False
    examples = []
    description = ''
    for line in help_str.splitlines():
        for tok in (',', '=', '>', '.',):
            line = line.replace(tok, ' ').strip()
        line = [_.strip() for _ in line.split()]
        if line and 'Description:' == line[0]:
            description = " ".join(line[1:])
        if line and tool_name == line[0]:
            examples = examples + [' '.join(line)]
            continue
        help_str = []
        params_in_line = 'parameters:' in line
        in_params = in_params or params_in_line

        if '-i' in line:
            args[('-i', '--input')] = 'Input file'

        if '-o' in line:
            args[('-o', '--output')] = 'Output file'
            continue

        parts = tuple(item for item in line if item[0] == '-')
        help_str = [item for item in line if item[0] != '-']
        if parts and in_params and not examples:
            if parts == ('-i',) or parts == ('-o',):
                continue
            args[parts] = " ".join(help_str)

    args[('--wd',)] = 'Working directory'
    if description:
        description = ' - {} '.format(description)
    help_tool = '{}{} Usage:\n\n\t'.format(tool, description)
    if examples:
        help_tool += '\n\t{}'.format(' '.join(_.strip() for _ in examples))
    if not to_parser:
        return args
    parser = argparse.ArgumentParser(description=help_tool)
    for k, v in args.items():
        print('ARGPARSE', k, v)
        v = v.replace('%', ' percent')
        v = re.sub('(\d)\s(\d+)', lambda x: '.'.join(x.groups()), v)
        required = '-i' in k or '-o' in k
        if '--inputs' in k:
            continue
        if '--filter' in k and ('--filterx' in k or '--filtery' in k):
            continue
        parser.add_argument(*k, help=v, required=required)
    return parser


def to_rust(tool, args):
    s = []
    delayed_load_later, kwargs = xarray_whitebox_io(globals()[tool], **vars(args))
    for k, v in kwargs.items():
        if v is not None:
            try:
                float(v)
                fmt = '--{}={}'
            except:
                if k in ('input', 'output', 'wd'):
                    if isinstance(v, (unicode, str)) and v != os.path.abspath(v):
                        v = os.path.join(os.path.abspath(os.curdir), v)
                        setattr(args, k, v)
                fmt = '--{}="{}"'
            s.append(fmt.format(k, v))
    if not 'wd' in vars(args):
        wd = os.path.abspath(os.curdir)
        s.append('--wd="{}"'.format(wd))
        setattr(args, 'wd', wd)
    return s, delayed_load_later


def call_whitebox_cli(tool, args=None, callback_func=None, silent=False):
    if callback_func is None:
        callback_func = partial(callback, silent=silent)
    wbt = WhiteboxTools()
    if not args:
        parser = convert_help_extract_params(tool, wbt, silent=silent)
        args = parser.parse_args()
    args, delayed_load_later = to_rust(tool, args)
    print('to_rust', args)
    if not silent:
        print(args)
    ret_val = wbt.run_tool(tool, args, callback_func)
    return delayed_load_later(ret_val)


def call_whitebox_func(tool, **kwargs):
    callback_func = kwargs.pop('callback_func', None)
    if not callback_func:
        callback_func = partial(callback, silent=True)
    args = argparse.Namespace(**kwargs)
    print('argparse', args)
    return call_whitebox_cli(tool, args=args, callback_func=callback_func)


def get_all_parsers():
    parsers = {}
    wbt = WhiteboxTools()
    for tool in tools:
        parsers[tool] = convert_help_extract_params(tool, wbt, silent=True)
    return parsers


def get_all_help(out=TOOL_DATA_FILE):
    tool_data = {}
    wbt = WhiteboxTools()
    for tool in tools:
        args = convert_help_extract_params(tool, wbt,
                                           to_parser=False,
                                           silent=True)
        args = [[list(k), v] for k, v in args.items()]
        tool_data[tool] = args
    with open(out, 'w') as f:
        f.write(json.dumps(tool_data, indent=2))
    return tool_data


HELP = get_all_help()

def _no_dash(p):
    if p[:2] == '--':
        return p[2:]
    elif p[0] == '-':
        return p[1:]
    else:
        raise ValueError('Expected a string but got {}'.format(p))


class WrappedWhiteBoxXArray(object):

    def __init__(self, tool):
        self.tool = partial(call_whitebox_func, tool, callback_func=partial(callback, silent=False))
        hlp = {tuple(k): v for k, v in HELP[tool]}
        self._ok_params = set()
        for k in hlp:
            for ki in k:
                self._ok_params.add(_no_dash(ki))
        hlp = '\n'.join('{}: {}'.format(', '.join(k), v) for k,v in sorted(hlp.items()))
        self.__doc__ = hlp

    def __call__(self, **kwargs):
        for k in kwargs:
            if not k in self._ok_params:
                raise ValueError('Parameter {} is not in {}'.format(k, self._ok_params))
        return self.tool(**kwargs)

    def __repr__(self):
        return self.__doc__

    __str__ = __repr__


for tool in tools:
    globals()[tool + 'Cli'] = partial(call_whitebox_cli, tool)
    globals()[tool] = WrappedWhiteBoxXArray(tool)

extras = [t + 'Cli' for t in tools]
extras += ['callback', 'tools', 'WhiteboxTools', 'get_all_help']
__all__ = tools + extras


