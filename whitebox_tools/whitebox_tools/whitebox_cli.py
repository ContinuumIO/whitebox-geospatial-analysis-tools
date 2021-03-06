from functools import partial, wraps
from itertools import chain
import argparse
import json
import os
import re
import string
import sys

from whitebox_tools.util import optional_imports_error
try:
    import numpy as np
    import xarray as xr
except:
    np = xr = None


from whitebox_tools.whitebox_base import WhiteboxTools, WHITEBOX_VERBOSE
from whitebox_tools.xarray_io import (xarray_whitebox_io,
                                      fix_path,
                                      WHITEBOX_TEMP_DIR,
                                      _is_input_field,
                                      _is_output_field)

try:
    unicode
except:
    unicode = str

TOOL_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'data',
                              'tool_data.json')
REFRESH_WHITEBOX_HELP = bool(int(os.environ.get('REFRESH_WHITEBOX_HELP', 0)))

listtools_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'data',
        'listtools.txt')
with open(listtools_file) as f:
    listtools = filter(None, (_.strip() for _ in f.read().splitlines()))
    listtools = (_.split(':') for _ in listtools)
    listtools = {k.strip(): v.strip() for k, v in listtools}
    tools = sorted(listtools)


# These are imported when doing * (more are available via CLI, e.g. wb-Max)
PYTHON_WHITEBOX = [
    'AdaptiveFilter',
    'Aspect',
    'AverageUpslopeFlowpathLength',
    'BalanceContrastEnhancement',
    'Basins',
    'BilateralFilter',
    'BlockMaximum',
    'BlockMinimum',
    'BreachDepressions',
    'BreachSingleCellPits',
    'BufferRaster',
    'Closing',
    'Clump',
    'ConservativeSmoothingFilter',
    'ConvertNodataToZero',
    'ConvertRasterFormat',
    'CostAllocation',
    'CostDistance',
    'CostPathway',
    'CreateColourComposite',
    'CreatePlane',
    'D8FlowAccumulation',
    'D8Pointer',
    'DInfFlowAccumulation',
    'DInfPointer',
    'Decrement',
    'DepthInSink',
    'DevFromMeanElev',
    'DiffFromMeanElev',
    'DiffOfGaussianFilter',
    'DirectDecorrelationStretch',
    'DirectionalRelief',
    'DistanceToOutlet',
    'DiversityFilter',
    'DownslopeDistanceToStream',
    'DownslopeFlowpathLength',
    'DownslopeIndex',
    'EdgeProportion',
    'ElevAbovePit',
    'ElevPercentile',
    'ElevRelativeToMinMax',
    'ElevRelativeToWatershedMinMax',
    'ElevationAboveStream',
    'EmbossFilter',
    'EuclideanAllocation',
    'EuclideanDistance',
    'ExtractStreams',
    'ExtractValleys',
    'FD8FlowAccumulation',
    'FD8Pointer',
    'FarthestChannelHead',
    'FetchAnalysis',
    'FillDepressions',
    'FillMissingData',
    'FillSingleCellPits',
    'FindMainStem',
    'FindNoFlowCells',
    'FindParallelFlow',
    'FindPatchOrClassEdgeCells',
    'FlightlineOverlap',
    'FlipImage',
    'FloodOrder',
    'FlowAccumulationFullWorkflow',
    'FlowLengthDiff',
    'GammaCorrection',
    'GaussianFilter',
    'GreaterThan',
    'HackStreamOrder',
    'HighPassFilter',
    'HighestPosition',
    'Hillshade',
    'Hillslopes',
    'HorizonAngle',
    'HortonStreamOrder',
    'Increment',
    'IntegerDivision',
    'IntegralImage',
    'JensonSnapPourPoints',
    'KNearestMeanFilter',
    'LaplacianFilter',
    'LaplacianOfGaussianFilter',
    'LasToAscii',
    'LeeFilter',
    'LengthOfUpstreamChannels',
    'LessThan',
    'LidarElevationSlice',
    'LidarGroundPointFilter',
    'LidarHillshade',
    'LidarIdwInterpolation',
    'LidarInfo',
    'LidarJoin',
    'LidarNearestNeighbourGridding',
    'LidarPointDensity',
    'LidarTile',
    'LidarTophatTransform',
    'LineDetectionFilter',
    'LineThinning',
    'LowestPosition',
    'MajorityFilter',
    'MaxBranchLength',
    'MaxDownslopeElevChange',
    'MaxElevationDeviation',
    'MaxOverlay',
    'MaxUpslopeFlowpathLength',
    'MaximumFilter',
    'MeanFilter',
    'MedianFilter',
    'MinAbsoluteOverlay',
    'MinDownslopeElevChange',
    'MinMaxContrastStretch',
    'MinimumFilter',
    'Modulo',
    'MultiscaleTopographicPositionImage',
    'NewRasterFromBase',
    'NormalVectors',
    'NormalizedDifferenceVegetationIndex',
    'NumDownslopeNeighbours',
    'NumInflowingNeighbours',
    'NumUpslopeNeighbours',
    'OlympicFilter',
    'Opening',
    'PanchromaticSharpening',
    'PennockLandformClass',
    'PickFromList',
    'PlanCurvature',
    'Power',
    'PrewittFilter',
    'ProfileCurvature',
    'RangeFilter',
    'RasterSummaryStats',
    'Reciprocal',
    'ReclassEqualInterval',
    'RelativeAspect',
    'RelativeStreamPowerIndex',
    'RelativeTopographicPosition',
    'RemoveOffTerrainObjects',
    'RemoveShortStreams',
    'RemoveSpurs',
    'RgbToIhs',
    'Rho8Pointer',
    'RobertsCrossFilter',
    'RuggednessIndex',
    'ScharrFilter',
    'SedimentTransportIndex',
    'ShreveStreamMagnitude',
    'SigmoidalContrastStretch',
    'Sink',
    'Slope',
    'SnapPourPoints',
    'SobelFilter',
    'SplitColourComposite',
    'StandardDeviationContrastStretch',
    'StandardDeviationFilter',
    'StrahlerOrderBasins',
    'StrahlerStreamOrder',
    'StreamLinkClass',
    'StreamLinkIdentifier',
    'StreamLinkLength',
    'StreamLinkSlope',
    'StreamSlopeContinuous',
    'Subbasins',
    'TangentialCurvature',
    'ThickenRasterLine',
    'ToDegrees',
    'ToRadians',
    'TophatTransform',
    'TopologicalStreamOrder',
    'TotalCurvature',
    'TotalFilter',
    'TraceDownslopeFlowpaths',
    'TributaryIdentifier',
    'Truncate',
    'TurningBandsSimulation',
    'Watershed',
    'WeightedSum',
    'WetnessIndex',
    'WriteFunctionMemoryInsertion',
    'ZScores',
]


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


def convert_help_extract_params(tool, wbt,
                                to_parser=True,
                                silent=False,
                                verbose=False):

    tool = tool.strip()
    args = {tuple(k): v for k, v in HELP[tool]}
    help_tool = listtools[tool]
    if not to_parser:
        return args
    parser = argparse.ArgumentParser(description=help_tool)
    for k, v in args.items():
        if '--inputs' in k:
            continue
        if '--filter' in k and ('--filterx' in k or '--filtery' in k):
            continue
        kw = dict(help=v)
        if ' flag ' in v or ' flag.' in v:
            kw['action'] = 'store_true'
        parser.add_argument(*k, **kw)
    return parser


def to_rust(tool, args):
    '''Convert arguments to formats expected by Rust'''
    optional_imports_error(np, xr)
    s = []
    outputs = (ki for k, v in HELP[tool] for ki in k)
    outputs = filter(lambda k: k.startswith('--'), outputs)
    outputs = tuple(_no_dash(k) for k in outputs
                    if _is_output_field(_no_dash(k)))
    for output in outputs:
        tok = ''.join(np.random.choice(tuple(string.ascii_letters)) for _ in range(7))
        fname = os.path.join(WHITEBOX_TEMP_DIR, '{}-{}.dep'.format(output, tok))
        vars(args)[output] = fix_path(fname)
    delayed_load_later, kwargs = xarray_whitebox_io(**vars(args))
    for k, v in kwargs.items():
        if isinstance(v, bool):
            s.append('--{}'.format(k))
            continue
        if v is not None:
            try:
                float(v)
                fmt = '--{}={}'
            except:
                if k == 'wd' or _is_input_field(k) or _is_output_field(k):
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


def call_whitebox_cli(tool, args=None,
                      callback_func=None, silent=False,
                      return_xarr=True,
                      verbose=WHITEBOX_VERBOSE):
    if callback_func is None:
        callback_func = partial(callback, silent=silent)
    wbt = WhiteboxTools()
    if not args:
        parser = convert_help_extract_params(tool, wbt,
                                             silent=True,
                                             verbose=verbose)
        args = parser.parse_args()
    args, delayed_load_later = to_rust(tool, args)
    ret_val = wbt.run_tool(tool, args, callback_func, verbose=verbose)
    if ret_val:
        raise ValueError('WhiteBox {0} (wb-{0}) failed with args: {1}'.format(tool, args))
    arr_or_dset = delayed_load_later(ret_val)
    if return_xarr:
        return arr_or_dset
    return ret_val


def call_whitebox_func(tool, **kwargs):
    callback_func = kwargs.pop('callback_func', None)
    if not callback_func:
        callback_func = partial(callback, silent=True)
    args = argparse.Namespace(**kwargs)
    return call_whitebox_cli(tool, args=args, callback_func=callback_func)


def get_all_parsers():
    parsers = {}
    wbt = WhiteboxTools()
    for tool in tools:
        parsers[tool] = convert_help_extract_params(tool, wbt, silent=True)
    return parsers


def get_all_help(out=TOOL_DATA_FILE, refresh=REFRESH_WHITEBOX_HELP):
    if not refresh:
        return json.load(open(TOOL_DATA_FILE))
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


def _fmt_help(tool):
    hlp = {tuple(k): v for k, v in HELP[tool]}
    ok_params = set()
    for k in hlp:
        for ki in k:
            ok_params.add(_no_dash(ki))
    hlp = '\n'.join('{}: {}'.format(', '.join(k), v) for k,v in sorted(hlp.items()))
    return hlp, ok_params


def validate_run(tool, **kwargs):
    _, ok_params = _fmt_help(tool)
    for k in kwargs:
        if not k in ok_params:
            raise ValueError('Parameter {} is not in {}'.format(k, ok_params))
    tool = partial(call_whitebox_func, tool, callback_func=partial(callback, silent=False))
    return tool(**kwargs)


for tool in tools:
    globals()[tool + 'Cli'] = partial(call_whitebox_cli, tool, return_xarr=False)

    class Wrapped(object):
        _tool = tool
        __doc__ = _fmt_help(tool)[0]
        def __call__(self, **kw):
            return validate_run(self._tool, **kw)

    globals()[tool] = Wrapped()


tool_names = [t + 'Cli' for t in tools] + PYTHON_WHITEBOX
__all__ = ['callback', 'tools',
           'WhiteboxTools', 'get_all_help'] + tool_names
