import os
import glob
from setuptools import setup, find_packages

import versioneer

version = versioneer.get_version()
cmdclass = versioneer.get_cmdclass()

def make_console_scripts():
    import whitebox_tools as wt
    scripts = []
    for tool in wt.tools:
        line = 'wb-{0} = whitebox_tools:{0}Cli'.format(tool)
        scripts.append(line)
    return scripts


setup(name='whitebox_tools',
      version=version,
      cmdclass=cmdclass,
      description='WhiteBox Tools',
      include_package_data=True,
      install_requires=[],
      packages=find_packages(),
      package_data={},
      entry_points={
        'console_scripts': make_console_scripts(), #['whitebox_tools = whitebox_tools.whitebox_cli:call_whitebox_cli'],
      }
    )
