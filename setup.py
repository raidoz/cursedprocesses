"""
cursedprocesses: Cursed processes.

Run multiple processes in parallel and get their output through a curses interface.
"""

from setuptools import setup, find_packages

import cursedprocesses

doclines = __doc__.split("\n")

setup(name='cursedprocesses',
      version=cursedprocesses.__version__,
      description='Cursed processes',
      long_description='\n'.join(doclines[2:]),
      url='https://github.com/raidoz/cursedprocesses',
      author='Raido Pahtma',
      author_email='authorfirstnamelastname@gmail.com',
      license='MIT',
      platforms=['any'],
      packages=find_packages(),
      install_requires=[''],
      entry_points={'console_scripts': ['cursedprocesses=cursedprocesses.runner:main']},
      zip_safe=False)
