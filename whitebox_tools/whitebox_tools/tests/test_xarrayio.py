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
                                      DEP_KEYS)
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

TESTDATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'testdata')
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


def pour_point_raster(as_xarr=True):
    arr = from_dep(EXAMPLE_DEMS[0])
    arr = arr.where(arr == arr.min())
    if as_xarr:
        return arr
    fname = os.path.join(WHITEBOX_TEMP_DIR, 'pour_pts')
    return data_array_to_dep(arr, fname=fname)[0]


def d8_example_test():
    d8_pntr = D8Pointer(input=from_dep(EXAMPLE_DEMS[0]))
    assert isinstance(d8_pntr, xr.DataArray)
    d8_flowacc = D8FlowAccumulation(input=d8_pntr)
    assert isinstance(d8_flowacc, xr.DataArray)
    w = Watershed(d8_pntr=d8_pntr, pour_pts=pour_point_raster())
    assert isinstance(w, xr.DataArray)


def make_synthetic_kwargs(tool, as_xarr=True):
    arg_spec_help = HELP[tool]
    kwargs = {}
    for arg_names, help_str in arg_spec_help:
        arg_name = [a[2:] for a in arg_names if '--' == a[:2]][0]
        if 'input' in arg_name and as_xarr:
            kwargs[arg_name] = from_dep(EXAMPLE_DEMS[0])
        elif 'input' in arg_name:
            kwargs[arg_name] = EXAMPLE_DEMS[0]
        if arg_name == 'inputs' and as_xarr:
            kwargs[arg_name] = xr.Dataset({x: from_dep(EXAMPLE_DEMS[0])
                                           for x in ('a', 'b')})
        elif arg_name == 'inputs':
            kwargs[arg_name] = ','.join(EXAMPLE_DEMS)
        elif 'output' == arg_name:
            kwargs['output'] = TO_REMOVE[0]
    return kwargs


as_xarray = (True, False)
tools_names_list = [(tool, as_xarr) for tool in tools
                    if tool not in ('D8FlowAccumulation', 'Watershed')
                    for as_xarr in as_xarray]
@pytest.mark.parametrize('tool, as_xarr', tools_names_list)
def test_each_tool(tool, as_xarr):
    if tool == 'WeightedSum':
        pytest.xfail('WeightedSum uses some delimiters for input/weights not handled yet')
    if tool == 'LidarInfo':
        pytest.skip('This is an interactive tool')
    if any('LAS' in xi for x in HELP[tool] for xi in x):
        pytest.xfail('LAS files are not tested yet with xarray')
    try:
        kwargs = make_synthetic_kwargs(tool, as_xarr=as_xarr)
        arr = globals()[tool](**kwargs)
        assert isinstance(arr, (xr.DataArray, xr.Dataset))
        assert 'kwargs' in arr.attrs
        assert set(arr.attrs.keys()) >= set(DEP_KEYS)
    finally:
        for r in TO_REMOVE:
            if os.path.exists(r):
                os.remove(r)


