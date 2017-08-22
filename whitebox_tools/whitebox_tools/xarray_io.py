
import os
import shutil
import string
import struct

import numpy as np
import xarray as xr

INPUT_ARGS = ['input', 'inputs', 'i', 'pour_pts',
              'd8_pntr', 'dem', 'input1', 'input2', 'input3',
              'i1', 'i2', 'i3', 'input_x', 'input_y',
              'streams', 'flow_accum', 'sca',
              'nir', 'red','blue', 'green', 'pan',
              'destination', 'base', 'seed_pts',
              'source','cost', 'slope',
              'flow_dir', 'comparison', 'linkid',
              'watersheds']
OUTPUT_ARGS = ['output', 'outputs', 'o']

WHITEBOX_TEMP_DIR = os.environ.get('WHITEBOX_TEMP_DIR')
DTYPES = {'float': 'f4',
          'integer': 'i2'}
ENDIAN = {'LITTLE_ENDIAN': '<',
          'BIG_ENDIAN': '>',}

OK_DATA_SCALES = ['continuous', 'categorical', 'Boolean', 'rgb']

OPTIONAL_DEP_FIELDS = ['display_min', 'display_max',
                       'metadata_entry', 'projection',
                       'preferred_palette',
                       'palette_nonlinearity', 'byte_order',
                       'nodata']
REQUIRED_DEP_FIELDS = ['max', 'min', 'north', 'south', 'east', 'west',
                       'cols', 'rows', 'dtype', 'z_units', 'xy_units',
                       'data_scale']
FLOAT_DEP_FIELDS = ['Min', 'Max',
                    'North', 'South', 'East', 'West',
                    'Display Min', 'Display Max']
INT_DEP_FIELDS = ['Cols', 'Rows', 'Stacks']
UPPER_STR_FIELDS = ['Data Type', 'Byte Order']

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
Stacks: {stacks}
Data Type:  {dtype}
Z Units:    {z_units}
Xy Units:   {xy_units}
Projection: {projection}
Data Scale: {data_scale}
Display Min:    {display_min}
Display Max:    {display_max}
Preferred Palette:  {preferred_palette}
Palette Nonlinearity: {palette_nonlinearity}
Nodata: {nodata}
Byte Order: {byte_order}
{metadata_entry}'''

DEP_KEYS = [x.split(':')[0].strip() for x in DEP_TEMPLATE.splitlines()
            if ':' in x]

def _is_output_field(field):
    is_out = field in OUTPUT_ARGS
    is_out2 = field.startswith('out_') and field != 'out_type'
    return is_out or is_out2


def _is_input_field(field):
    return field in INPUT_ARGS


def not_2d_error():
    raise NotImplementedError('Only 2-D rasters are supported by xarray wrapper currently')


def _lower_key(k):
    return '_'.join(k.lower().split())


def _assign_nodata(arr):
    attrs = arr.attrs
    no_data = [v for k, v in attrs.items()
               if k.lower() == 'nodata']
    if not no_data:
        return arr
    no_data = np.float64(no_data[0])
    if 'int' in arr.dtype.name:
        arr.values = arr.values.astype(np.float64)
    arr.values[arr.values == no_data] = np.NaN
    return arr


def assign_nodata(dset_or_arr):
    if isinstance(dset_or_arr, xr.Dataset):
        for k, v in dset_or_arr.data_vars.items():
            _assign_nodata(v)
    else:
        _assign_nodata(dset_or_arr)
    return dset_or_arr


class MissingDepMetadata(ValueError):
    pass


def case_insensitive_attrs(attrs, typ):
    lower = {'dtype': typ}
    for k, v in attrs.items():
        lower[_lower_key(k)] = v
    if 'xy_units' not in lower and 'units' in lower:
        lower['xy_units'] = lower['units']
    if 'z_units' not in lower and 'units' in lower:
        lower['z_units'] = lower['units']
    if not 'preferred_palette' in lower:
        lower['palette_nonlinearity'] = 'high_relief.pal'
    if not 'palette_nonlinearity' in lower:
        lower['palette_nonlinearity'] = 1.
    has_keys = set(lower)
    needs_keys = set(REQUIRED_DEP_FIELDS)
    if not has_keys >= needs_keys:
        missing = needs_keys - has_keys
        raise MissingDepMetadata('Did not find the following keys in DataArray: {} (found {})'.format(missing, lower))
    for k in OPTIONAL_DEP_FIELDS:
        if k not in lower:
            lower[k] = ''
    data_scale = (lower.get('data_scale') or '').lower()
    if not data_scale in OK_DATA_SCALES:
        raise MissingDepMetadata('Data Scale (data_scale) is not in {} - attrs: {}'.format(OK_DATA_SCALES, lower))
    if data_scale == 'rgb':
        raise NotImplementedError('RGB DataArrays are not handled yet - serialize first, then run command line WhiteBox tool')
    return lower


def fix_path(path):
    '''Handle commas and semicolons in paths for >1 input file'''
    if ';' in path:
        paths = path.split(';')
    else:
        paths = path.split(', ')
    paths = [os.path.abspath(os.path.join(os.curdir, path))
             for path in paths]
    if len(paths) == 1:
        return paths[0]
    return ', '.join(paths)


def to_tas(vals, typ_str, fname):
    '''Dump array to .tas file
    Parameters:
        vals: numpy array, typicall 2D
        typ_str: "integer" or "float"
        fname: output path
    Returns:
        None
    '''
    if vals.ndim != 2:
        not_2d_error()
    r, c = vals.shape
    if typ_str == 'integer':
        abbrev = 'h'
    else:
        abbrev = 'f'
    with open(fname, 'wb') as f:
        for i in range(r):
            f.write(struct.pack(abbrev * c, *vals[i, :]))


def _from_dep(fname):
    '''Load just the .dep file's metadata, not the .tas'''
    with open(fname) as f:
        content = f.read()
    attrs = {}
    for line in content.splitlines():
        parts = line.strip().split(':')
        key, value = parts[0], ':'.join(parts[1:]).strip()
        key = key.strip().title()
        if key in INT_DEP_FIELDS:
            value = int(value)
        elif key in FLOAT_DEP_FIELDS:
            value = float(value)
        elif key not in UPPER_STR_FIELDS:
            value = value.upper()
        if key == 'Metadata Entry':
            if not key in attrs:
                attrs[key] = value
            else:
                attrs[key] += '\n' + value
        else:
            attrs[key] = value
    return attrs


def _get_dtype(dtype_str):
    '''map numpy type to .dep Data Type'''
    if 'float' in dtype_str.lower():
        return ('float', DTYPES['float'])
    else:
        return ('integer', DTYPES['integer'])


def from_dep(dep, tas=None):
    '''Load a .dep file and corresponding .tas file

    Parameters:
       dep:  Path to a .dep file
       tas:  Optional path to .tas file or guessed from .dep
    Returns:
       arr:  xarray.DataArray

    '''
    if not isinstance(dep, strings) or not os.path.exists(dep):
        raise ValueError('File {} does not exist'.format(dep))
    if not tas and dep.endswith('.dep'):
        tas = dep[:-4] + '.tas'
    if not tas or not os.path.exists(tas):
        raise ValueError('Expected .tas file at {} (guessed from {})'.format(tas, dep))
    attrs = _from_dep(dep)
    _, dtype = _get_dtype(attrs.get('Data Type'))
    byte_order = attrs.get('byte_order')
    if byte_order in ENDIAN:
        dtype = ENDIAN[byte_order] + dtype
    val = np.fromfile(tas, dtype=dtype)
    val.resize(attrs['Rows'], attrs['Cols'])
    attrs['filename'] = [dep, tas]
    dims = ('y', 'x')
    y = np.linspace(attrs['South'], attrs['North'], attrs['Rows'] + 1)[:-1]
    x = np.linspace(attrs['East'], attrs['West'], attrs['Cols'] + 1)[:-1]
    coords = dict((('x', x), ('y', y)))
    return xr.DataArray(val, coords=coords, dims=dims, attrs=attrs)


def data_array_to_dep(arr, fname=None, tag=None, **dep_kwargs):
    '''Dump a DataArray to fname or a tag (for temp dir)

    Parameters:
        arr: DataArray with the attrs composed of .dep
             fields
        fname: File name
        tag: shorthand tag for use with temp dir
    Returns:
        (dep_file_name, tas_file_name) tuple
    '''
    val = arr.values
    typ_str, dtype = _get_dtype(val.dtype.name)
    val = val.astype('<' + dtype)
    try:
        attrs = case_insensitive_attrs(arr.attrs, typ_str)
    except MissingDepMetadata:
        arr = add_dep_meta(arr, **dep_kwargs)
        attrs = case_insensitive_attrs(arr.attrs, typ_str)
    attrs['byte_order'] = 'LITTLE_ENDIAN'
    if val.ndim != 2 or attrs.get('stacks') > 1:
        not_2d_error()
    if not fname:
        tag = str(tag)
        fname = os.path.join(WHITEBOX_TEMP_DIR, tag)
    dep, tas = fname + '.dep', fname + '.tas'
    with open(dep, 'w') as f:
        metadata_entry = attrs.get('metadata_entry', '')
        at = attrs.copy()
        at['metadata_entry'] = ''.join('\nMetadata Entry: {}'.format(m)
                                       for m in metadata_entry.splitlines())
        f.write(DEP_TEMPLATE.format(**at))
    to_tas(val, typ_str, tas)
    return dep, tas


def xarray_whitebox_io(**kwargs):
    '''Returns a callable to be used after WhiteBox tool runs -
    the callable returns an xarray.DataArray or Dataset

    Parameters:
       kwargs:  Keyword arguments to the tool, e.g. --dem
    Returns:
       tuple of (func, kwargs) where kwargs are input
           kwargs modified in place
    '''
    load_afterwards = {}
    delete_tempdir = kwargs.pop('delete_tempdir', True)
    fnames = {}
    dumped_an_xarray = used_str = False
    for k, v in kwargs.items():
        if _is_input_field(k):
            if isinstance(v, strings):
                kwargs[k] = fix_path(v)
                used_str = True
            elif isinstance(v, xr.Dataset):
                if k in ('input', 'dem'):
                    raise ValueError('Cannot use xarray.Dataset unless the tool allows --inputs.  Here --input was used, and the tool must be called for each xarray.DataArray')
                for k2 in v.data_vars:
                    data_arr = getattr(v, k2)
                    dep, tas = data_array_to_dep(data_arr, tag=k2)
                    fnames[(k, k2)] = [dep, tas]
                kwargs[k] = ', '.join(dep for (k1, k2), (dep, tas) in fnames.items()
                                      if k1 == k)
                dumped_an_xarray = k
            elif isinstance(v, xr.DataArray):
                kwargs[k] = data_array_to_dep(v, tag=k)[0]
                dumped_an_xarray = k
        elif _is_output_field(k):
            load_afterwards[k] = fix_path(v)
    def delayed_load_later(ret_val):
        if not load_afterwards:
            return ret_val
        data_arrs = {}
        attrs = dict(kwargs=kwargs, return_code=ret_val)

        for k, paths in load_afterwards.items():
            for path in paths.split(', '):
                data_arrs[k] = from_dep(path)
                data_arrs[k].attrs.update(attrs)
        dset = assign_nodata(xr.Dataset(data_arrs, attrs=attrs))
        for dep, tas in fnames.values():
            for fname in (dep, tas):
                os.remove(fname)
        if len(load_afterwards) == 1:
            return dset[k] # DataArray
        return dset        # Dataset - TODO implment later for multi output?
    return delayed_load_later, kwargs



def add_dep_meta(arr,
                 projection='not specified',
                 display_max=None,
                 display_min=None,
                 data_scale='continuous',
                 z_units='meters',
                 xy_units='meters',
                 x_coord_name='x',
                 y_coord_name='y',
                 no_data=None,
                 palette='high_relief.pal',
                 palette_nonlinearity=1.0):
    if not isinstance(arr, xr.DataArray):
        raise ValueError('Expected a DataArray')
    v = arr.values

    if not v.ndim == 2:
        raise ValueError('Expected a 2-D raster (3-D array NotImplemented)')
    if no_data is None:
        if np.any(np.isnan(v)):
            raise ValueError('DataArray has NaN but no_data was not provided (NaN fill value for .dep file)')
    else:
        v[np.isnan(v)] = no_data
    y = getattr(arr, y_coord_name).values
    x = getattr(arr, x_coord_name).values
    if 'float' in v.dtype.name:
        dtype_str = 'float'
        dtype = '<f4'
    else:
        dtype_str = 'integer'
        dtype_str = '<2'
    dep_file = {
        'Min': v.min(), 'Max': v.min(),
        'North': y.max(), 'South': y.min(),
        'East': x.min(), 'West': x.max(),
        'Cols': v.shape[1], 'Rows': v.shape[0],
        'Stacks': 1, 'Data Type': dtype,
        'Z Units': 'meters','Xy Units': 'meters',
        'Projection': projection, 'Data Scale': data_scale,
        'Display Min': display_min, 'Display Max': display_max,
        'Preferred Palette': palette,
        'Palette Nonlinearity': palette_nonlinearity,
        'Nodata': no_data,
        'Byte Order': 'LITTLE_ENDIAN'
    }
    arr.attrs.update(dep_file)
    return arr

