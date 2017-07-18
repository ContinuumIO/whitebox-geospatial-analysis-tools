
import os
import shutil
import struct

import numpy as np
import xarray as xr

INPUT_ARGS = ['input', 'inputs', 'i']
OUTPUT_ARGS = ['output', 'outputs', 'o']
WHITEBOX_TEMP_DIR = os.environ.get('WHITEBOX_TEMP_DIR')
if not WHITEBOX_TEMP_DIR:
    WHITEBOX_TEMP_DIR = os.path.expanduser('~/.whitebox_tools_tempdir')
    if not os.path.exists(WHITEBOX_TEMP_DIR):
        os.mkdir(WHITEBOX_TEMP_DIR)
if not os.path.exists(WHITEBOX_TEMP_DIR):
    raise ValueError('{} does not exist - Define environment variable: WHITEBOX_TEMP_DIR'.format(WHITEBOX_TEMP_DIR))

try:
    strings = (str, unicode)
except:
    strings = (str,)

DEP_TEMPLATE = '''Min:  {min}
Max:    {max}
North:  {north}
South:  {south}
East:   {east}
West:   {west}
Cols:   {cols}
Rows:   {rows}
Data Type:  {dtype}
Z Units:    {z_units}
XY Units:   {xy_units}
Projection: {proj}
Data Scale: {data_scale}
Display Min:    {display_min}
Display Max:    {display_max}
Preferred Palette:  {palette}
{metadata_entry}'''

DTYPES = {'float': np.float32,
          'integer': np.int16}

OK_DATA_SCALES = ['continuous', 'categorical', 'Boolean', 'rgb']

OPTIONAL_DEP_FIELDS = ['display_min', 'display_max',
                       'metadata_entry', 'proj', 'palette']
REQUIRED_DEP_FIELDS = ['max', 'min', 'north', 'south', 'east', 'west',
                       'cols', 'rows', 'dtype', 'z_units', 'xy_units',
                       'data_scale']
FLOAT_DEP_FIELDS = ['Min', 'Max',
                    'North', 'South', 'East', 'West',
                    'Display Min', 'Display Max']
INT_DEP_FIELDS = ['Cols', 'Rows',]

def case_insensitive_attrs(attrs, typ):
    lower = {'dtype': typ}
    for k, v in attrs.items():
        k = k.lower()
        lower[k] = v
    if 'xy_units' not in lower and 'units' in lower:
        lower['xy_units'] = lower['units']
    if 'z_units' not in lower and 'units' in lower:
        lower['z_units'] = lower['units']
    has_keys = set(lower)
    needs_keys = set(REQUIRED_DEP_FIELDS)
    if not has_keys >= needs_keys:
        missing = needs_keys - has_keys
        raise ValueError('Did not find the following keys in DataArray: {} (found {})'.format(missing, lower))
    for k in OPTIONAL_DEP_FIELDS:
        if k not in lower:
            lower[k] = ''
    if not lower.get('data_scale') in OK_DATA_SCALES:
        raise ValueError('Data Scale (data_scale) is not in {} - attrs: {}'.format(OK_DATA_SCALES, lower))
    if lower.get('data_scale') == 'rgb':
        raise NotImplementedError('RGB DataArrays are not handled yet - serialize first, then run command line WhiteBox tool')
    return lower


def fix_path(path):
    paths = path.split(', ')
    return [os.path.abspath(os.path.join(os.curdir, path))
            for path in paths]


def to_tas(vals, typ, fname):
    r, c = vals.shape
    if typ == 'integer':
        abbrev = 'h'
    else:
        abbrev = 'f'
    with open(fname, 'wb') as f:
        for i in range(r):
            f.write(struct.pack(abbrev * c, *vals[i, :]))


def from_dep(fname):
    with open(fname) as f:
        content = f.read()
    attrs = {}
    for line in content.splitlines():
        parts = line.strip().split(':')
        key, value = parts[0], ':'.join(parts[1:])
        key = key.strip().title()
        if key in INT_DEP_FIELDS:
            value = int(value)
        elif key in FLOAT_DEP_FIELDS:
            value = float(value)
        attrs[key] = value
    return attrs


def from_tas_and_dep(dep, tas=None):
    if not tas and dep.endswith('.dep'):
        tas = dep[:-4] + '.tas'
    if not tas or not os.path.exists(tas):
        raise ValueError('Expected .tas file at {} (guessed from {})'.format(tas, dep))
    attrs = from_dep(dep)
    val = np.fromfile(tas)
    attrs['filename'] = [dep, tas]
    dims = ('x', 'y')
    y = np.linspace(attrs['South'], attrs['North'], attrs['Rows'] + 1)[:-1]
    x = np.linspace(attrs['East'], attrs['West'], attrs['Cols'] + 1)[:-1]
    coords = [('x', x), ('y', y)]
    return xr.DataArray(val, coords=coords, dims=dims, attrs=attrs)


def data_array_to_dep(arr, tag):
    tag = str(tag)
    val = arr.values
    if 'float' in val.dtype.name:
        typ = 'float'
        val = val.astype(np.float32)
    else:
        typ = 'integer'
        val = val.astype(np.int16)
    attrs = case_insensitive_attrs(arr.attrs, typ)
    fname = os.path.join(WHITEBOX_TEMP_DIR, tag)
    dep, tas = fname + '.dep', fname + '.tas'
    with open(dep, 'w') as f:
        f.write(DEP_TEMPLATE.format(**attrs))
    to_tas(val, typ, tas)
    return dep, tas


def xarray_whitebox_io(func, **kwargs):
    load_afterwards = {}
    delete_tempdir = kwargs.pop('delete_tempdir', True)
    fnames = {}
    for k, v in kwargs.items():
        if k in INPUT_ARGS:
            if isinstance(v, strings):
                kwargs[k] = fix_path(v)
            elif isinstance(v, xr.Dataset):
                for k2 in v.data_vars:
                    data_arr = getattr(v, k2)
                    dep, tas = data_array_to_dep(arr, k2)
                    fnames[(k, k2)] = [dep, tas]
                kwargs[k] = ', '.join(dep for (k1, k2), (dep, tas) in fnames.items()
                                      if k1 == k)
            elif isinstance(v, xr.DataArray):
                kwargs[k] = data_array_to_dep(v, k)
        elif k in OUTPUT_ARGS:
            load_afterwards[k] = fix_path(v)
    ret_val = func(**kwargs)
    if ret_val:
        raise ValueError('{} ({}) failed with return code {}'.format(func, kwargs, ret_val))
    data_arrs = {}
    for k, paths in load_afterwards.items():
        for path in v:
            data_arrs[k] = from_tas_and_dep(path)
    attrs = dict(kwargs=kwargs, return_code=ret_val)
    dset = xr.Dataset(data_arrs, attrs=attrs)
    for dep, tas in fnames.values():
        for fname in (dep, tas):
            os.remove(fname)
    return dset

