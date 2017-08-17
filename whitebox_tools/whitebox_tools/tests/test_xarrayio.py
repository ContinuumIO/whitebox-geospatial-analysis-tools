import os

import numpy as np
import pytest
import xarray as xr

from whitebox_tools.whitebox_cli import * # __all__ is defined there
from whitebox_tools.xarray_io import (from_dep,
                                      data_array_to_dep,
                                      WHITEBOX_TEMP_DIR,
                                      xarray_whitebox_io,
                                      INPUT_ARGS,
                                      DEP_KEYS,
                                      _is_input_field,
                                      _is_output_field)
try:
    unicode
except:
    unicode = str
HELP = get_all_help()

DEFAULT_ATTRS = {
    'south': 0,
    'north': 1,
    'east': -1,
    'west': 1,
    'data_scale': 'continuous',
    'rows': 'FILL_OUT_LATER',
    'cols': 'FILL_OUT_LATER',
    'xy_units': 'meters',
    'z_units': 'meters',
    'min': 0.,
    'max': 10.,
}

# TODO - address arg spec or related issues for the following
# tools:
XFAIL = ('DownslopeIndex',
         'DirectDecorrelationStretch', # uses RGB image
         'SplitColourComposite', # RGB usage not supported
         'StreamSlopeContinuous',# has a required "--streams" arg
         'SedimentTransportIndex',# has a required "--sca" arg
         'NormalizedDifferenceVegetationIndex', #nir and red needed
         'RandomField', # not sure of problem
         'PanchromaticSharpening', # has 'red','blue', 'green', 'pan' args
         'TurningBandsSimulation',
         'DirectDecorrelationStretch',
         'PickFromList',
         'RgbToIhs',
         'PercentageContrastStretch',
         'CreateColourComposite',
         'MultiscaleTopographicPositionImage',
         'MinMaxContrastStretch',
         'NewRasterFromBase',
         'MaxElevationDeviation')


TESTDATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'testdata')
if not os.path.exists(TESTDATA):
    TESTDATA = os.environ.get('WHITEBOX_DATA_DIR', 'not-there')
    if not os.path.exists(TESTDATA):
        raise ValueError('Define WHITEBOX_DATA_DIR to be the testdata folder of .dep files')
EXAMPLE_DEMS = tuple(os.path.join(TESTDATA, f) for f in ('DEM.dep', 'DEV_101.dep'))
TO_REMOVE = ['test-output.{}'.format(end) for end in ('dep', 'tas')]

@pytest.mark.parametrize('dem', EXAMPLE_DEMS)
def test_xarray_serde_works(dem):
    arr = from_dep(dem)
    out = os.path.join(WHITEBOX_TEMP_DIR, 'out.dep')
    dep_out, tas_out = data_array_to_dep(arr, fname=out)
    arr2 = from_dep(dep_out)
    assert arr.shape == arr2.shape
    assert np.all(arr.values == arr2.values)
    missing = set(k for k in arr.attrs if not k in arr2.attrs)
    assert not missing or (missing == {'Metadata Entry'})
    for k, v in arr.attrs.items():
        if k in ('filename',): continue
        v2 = arr2.attrs.get(k)
        if isinstance(v, (str, unicode)):
            assert isinstance(v2, (str, unicode)), repr((k, v, v2))
            v, v2 = v.lower(), v2.lower()
        msg = 'With key {}, {} != {}'.format(k, v, v2)
        assert v == v2, msg


def pour_point_raster(dem=None, as_xarr=True):
    if dem is None:
        dem = from_dep(EXAMPLE_DEMS[0])
    pour_pts = dem.where(dem == dem.min())
    if as_xarr:
        return dem
    fname = os.path.join(WHITEBOX_TEMP_DIR, 'pour_pts')
    return data_array_to_dep(dem, fname=fname)[0]


def d8_pntr(dem=None):
    if dem is None:
        dem = from_dep(EXAMPLE_DEMS[0])
    return dem, D8Pointer(dem=dem)

def flow_accumulation(dem=None):
    if dem is None:
        dem = from_dep(EXAMPLE_DEMS[0])
    filled_dem = FillDepressions(dem=dem)
    slope = Slope(input=filled_dem, zfactor=1.)
    sca = D8FlowAccumulation(dem=filled_dem, out_type='sca')
    flow_accum_cells = D8FlowAccumulation(dem=filled_dem, out_type='cells')
    flow_accum = D8FlowAccumulation(dem=filled_dem, out_type='ca')
    streams = ExtractStreams(flow_accum=sca, threshold=100)
    return xr.Dataset({'streams': streams,
                       'slope': slope,
                       'sca': sca,
                       'flow_accum_cells': flow_accum_cells,
                       'flow_accum': flow_accum,
                       'dem': dem,
                       'filled_dem': filled_dem})

def wshed():
    dem, d8 = d8_pntr()
    w = Watershed(d8_pntr=d8, pour_pts=pour_point_raster(dem))
    dset = xr.Dataset(dict(dem=dem,
                           d8_pntr=d8,
                           watersheds=w,
                           flow_dir=d8))
    dset = xr.merge((dset, flow_accumulation(dem)))
    return dset

INPUT_ARRS = wshed()


def test_stream_link_slope():
    linkid = StreamLinkIdentifier(d8_pntr=INPUT_ARRS.d8_pntr,
                                  streams=INPUT_ARRS.streams,
                                  output='linkid.dep')
    assert isinstance(linkid, xr.DataArray)
    link_slope = StreamLinkSlope(linkid=linkid,
                                 d8_pntr=INPUT_ARRS.d8_pntr,
                                 dem=INPUT_ARRS.filled_dem)
    assert isinstance(link_slope, xr.DataArray)

def test_FlowAccumulationFullWorkflow():
    kw = dict(out_accum='out_accum.dep',
              out_dem='out_dem.dep',
              out_type='sca',
              dem=INPUT_ARRS.dem,
              clip=True,
              out_pntr=INPUT_ARRS.d8_pntr)
    out = FlowAccumulationFullWorkflow(**kw)
    assert isinstance(out, xr.Dataset)
    var = tuple(out.data_vars)
    for k in kw:
        if 'out_' in k and 'out_type' != k:
            assert k in var


def test_wetness_index():
    '''
    wb-D8FlowAccumulation --dem testdata/DEM.dep  --out_type sca -o sca.dep
    wb-WetnessIndex --sca sca.dep --slope slope.dep -o wetness_index.dep

    '''
    wet = WetnessIndex(sca=INPUT_ARRS.sca,
                       slope=INPUT_ARRS.slope)
    assert isinstance(wet, xr.DataArray)


def test_cost_dist_alloc():
    pytest.xfail('This test is too slow (change input data)')
    cost = INPUT_ARRS.dem * 0.1
    source = INPUT_ARRS.dem * 1.1
    cost.attrs.update(INPUT_ARRS.dem.attrs)
    source.attrs.update(INPUT_ARRS.dem.attrs)
    out = CostDistance(source=INPUT_ARRS.dem,
                 cost=cost,
                 out_backlink='out_backlink.dep',
                 out_accum='out_accum.dep')
    alloc = CostAllocation(source=source,
                           backlink=out.out_backlink)
    assert isinstance(cost_alloc, xr.DataArray)


def test_full_workflow():
    kw = dict(dem=INPUT_ARRS.dem,
              out_dem='filled.dep',
              out_accum='flow_accum.dep',
              out_type='sca',
              out_pntr='d8_pntr.dep')
    out = FlowAccumulationFullWorkflow(**kw)
    assert isinstance(out, xr.Dataset)
    for k in ('dem', 'accum', 'pntr'):
        assert 'out_{}'.format(k) in out.data_vars



def make_synthetic_kwargs(tool, as_xarr=True):
    arg_spec_help = HELP[tool]
    kwargs = {}

    for arg_names, help_str in arg_spec_help:
        arg_name = [a[2:] for a in arg_names if '--' == a[:2]]
        if arg_name:
            arg_name = arg_name[0]
        else:
            arg_name = arg_names[0].replace('-', '')
        if tool in ('PennockLandformClass', 'RemoveOffTerrainObjects',):
            if arg_name == 'slope':
                kwargs['slope'] = 0.008 # not slope raster but threshold
                continue
        if tool == 'WeightedSum':
            if arg_name == 'weights':
                kwargs['weights'] = ';'.join(str(x) for x in range(1, 1 + len(EXAMPLE_DEMS)))
                continue
        if arg_name in INPUT_ARRS:
            kwargs[arg_name] = INPUT_ARRS[arg_name]
        elif arg_name == 'inputs':
            kwargs[arg_name] = ','.join(EXAMPLE_DEMS)
        elif arg_name == 'inputs' and as_xarr:
            kwargs[arg_name] = xr.Dataset({x: from_dep(EXAMPLE_DEMS[0])
                                           for x in ('a', 'b')})
        elif arg_name == 'd8_pntr':
            kwargs[arg_name] = INPUT_ARRS.d8_pntr
        elif _is_input_field(arg_name) and as_xarr:
            kwargs[arg_name] = INPUT_ARRS.dem
        elif _is_input_field(arg_name):
            kwargs[arg_name] = EXAMPLE_DEMS[0]
        elif _is_output_field(arg_name):
            kwargs[arg_name] = arg_name
    return kwargs


as_xarray = (True, False)
tools_names_list = [(tool, as_xarr) for tool in tools
                    if tool not in ('D8FlowAccumulation', 'Watershed')
                    for as_xarr in as_xarray]
@pytest.mark.parametrize('tool, as_xarr', tools_names_list)
def test_each_tool(tool, as_xarr):
    if tool == 'RasterSummaryStats' and as_xarr:
        return # no returned array
    if tool.startswith(('Cost', 'Wetness',
                       'StreamLink',
                       'FlowAccumulationFullWorkflow')):
        return # tested elsewhere
    if tool in XFAIL:
        pytest.xfail('Tool {} is not yet supported'.format(tool))
    if tool == 'LidarInfo':
        pytest.skip('This is an interactive tool')
    if any('LAS' in xi for x in HELP[tool] for xi in x):
        pytest.xfail('LAS files are not tested yet with WhiteBox tools + xarray')
    try:
        kwargs = make_synthetic_kwargs(tool, as_xarr=as_xarr)
        arr = globals()[tool](**kwargs)
        if as_xarr:
            assert isinstance(arr, (xr.DataArray, xr.Dataset))
            assert 'kwargs' in arr.attrs
            assert set(arr.attrs.keys()) >= set(DEP_KEYS)

    finally:
        for r in TO_REMOVE:
            if os.path.exists(r):
                os.remove(r)


