
from __future__ import print_function

import sys


def optional_imports_error(np, xr):
    if np is None:
        print('NumPy is required: conda install numpy', file=sys.stderr)
        raise
    if xr is None:
        print('XArray is required: conda install xarray', file=sys.stderr)
        raise
