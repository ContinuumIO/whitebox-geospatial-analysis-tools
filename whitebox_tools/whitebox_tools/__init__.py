__import__('pkg_resources').declare_namespace('whitebox_tools')
from whitebox_tools._version import get_versions
__version__ = get_versions()['version']
del get_versions
from whitebox_tools.whitebox_cli import *
