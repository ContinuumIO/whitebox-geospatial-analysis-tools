import argparse
from functools import partial
from itertools import chain
import os
import re
import sys

from whitebox_tools.whitebox_base import WhiteboxTools

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
def callback(out_str):
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
                print('{0} {1}%'.format(label, progress), end="\r")
            else:
                callback.prev_line_progress = True
                print(out_str)
        elif "error" in out_str.lower():
            print("ERROR: {}".format(out_str))
            callback.prev_line_progress = False
        elif "elapsed time (excluding i/o):" in out_str.lower():
            elapsed_time = ''.join(
                ele for ele in out_str if ele.isdigit() or ele == '.')
            units = out_str.lower().replace("elapsed time (excluding i/o):",
                                            "").replace(elapsed_time, "").strip()
            print("Elapsed time: {0}{1}".format(elapsed_time, units))
            callback.prev_line_progress = False
        else:
            if callback.prev_line_progress:
                print('\n{0}'.format(out_str))
                callback.prev_line_progress = False
            else:
                print(out_str)

    except:
        print(out_str)

def convert_help_extract_params(tool, wbt, to_parser=True):
    tool = tool.strip()
    help_str = "\n".join(wbt.tool_help(tool, silent=True))
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
        required = '-i' in k or '-o' in k
        if '--inputs' in k:
            continue
        if '--filter' in k and ('--filterx' in k or '--filtery' in k):
            continue
        parser.add_argument(*k, help=v, required=required)
    return parser

def to_rust(tool, args):
    s = []
    for k, v in vars(args).items():
        s.append('--{}={}'.format(k, v))
    return s

def call_whitebox_cli(tool, args=None, callback_func=None):
    if callback_func is None:
        callback_func = callback
    wbt = WhiteboxTools()
    if not args:
        parser = convert_help_extract_params(tool, wbt)
        args = parser.parse_args()
    args = to_rust(tool, args)
    print(args)
    return wbt.run_tool(tool, args, callback_func)


def call_whitebox_func(tool, **kwargs):
    callback_func = kwargs.pop('callback_func', callback)
    args = argparse.Namespace(**kwargs)
    return call_whitebox_cli(tool, args=args, callback_func=callback_func)

def get_all_parsers():
    parsers = {}
    wbt = WhiteboxTools()
    for tool in tools:
        parsers[tool] = convert_help_extract_params(tool, wbt)
    return parsers


for tool in tools:
    globals()[tool + 'Cli'] = partial(call_whitebox_cli, tool)
    globals()[tool] = partial(call_whitebox_func, tool)

extras = [t + 'Cli' for t in tools]
__all__ = tools + ['callback', 'tools', 'WhiteboxTools'] + extras


