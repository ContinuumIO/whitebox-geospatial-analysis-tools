import os

import numpy as np
import pytest
import xarray as xr

from whitebox_tools.whitebox_cli import * # __all__ is defined there
from whitebox_tools.xarray_io import (from_dep,
                                      data_array_to_dep,
                                      WHITEBOX_TEMP_DIR,
                                      xarray_whitebox_io,)
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
def test_xarray_io_serde_works(dem):
    arr = from_dep(dem)
    out = os.path.join(WHITEBOX_TEMP_DIR, 'out.dep')
    dep_out, tas_out = data_array_to_dep(arr, fname=out)
    arr2 = from_dep(dep_out)
    assert arr.shape == arr2.shape
    assert np.all(arr.values == arr2.values)
    assert set(arr.attrs) ^ set(arr2.attrs) == set()
    assert np.all(np.array(sorted(arr.attrs)) == np.array(sorted(arr2.attrs)))
    for k, v in arr.attrs.items():
        if k in ('filename',): continue
        v2 = arr2.attrs.get(k)
        if isinstance(v, (str, unicode)):
            v, v2 = v.lower(), v2.lower()
        msg = 'With key {}, {} != {}'.format(k, v, v2)
        assert v == v2, msg


def pour_point_raster(arr):
    return arr.copy(deep=True).where(arr == arr.min())


def make_synthetic_kwargs(tool, as_xarr=True):
    arg_spec_help = HELP[tool]
    kwargs = {}
    for arg_names, help_str in arg_spec_help:
        print('an', arg_names,)
        arg_name = [a[2:] for a in arg_names if '--' == a[:2]][0]
        if 'input' == arg_name and as_xarr:
            kwargs[arg_name] = from_dep(EXAMPLE_DEMS[0])
        elif 'input' == arg_name:
            kwargs[arg_name] = EXAMPLE_DEMS[0]
        elif 'output' == arg_name:
            kwargs['output'] = TO_REMOVE[0]
        elif 'pour_pts' == arg_name:
            kwargs[arg_name] = pour_point_raster()
    return kwargs


as_xarray = (True, False)
tools_names_list = [(tool, as_xarr) for tool in tools for as_xarr in as_xarray]
@pytest.mark.parametrize('tool, as_xarr', tools_names_list)
def test_each_tool(tool, as_xarr):
    if tool == 'WeightedSum':
        pytest.xfail('WeightedSum uses some delimiters for input/weights not handled yet')
    try:
        kwargs = make_synthetic_kwargs(tool, as_xarr=as_xarr)
        out = globals()[tool](**kwargs)
        assert isinstance(out, xr.Dataset)
        assert tuple(out.data_vars) == ('output',)
        arr = out.output
        assert 'kwargs' in out.attrs
    finally:
        for r in TO_REMOVE:
            if os.path.exists(r):
                os.remove(r)


