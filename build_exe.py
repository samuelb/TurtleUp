from distutils.core import setup
import py2exe, sys, os

VERSION = '0.9'

if os.path.exists('dist/TurtleUp_%s.exe' % VERSION):
    os.unlink('dist/TurtleUp_%s.exe' % VERSION)

sys.argv.append('py2exe')

setup(
    options = {'py2exe': {
                    'bundle_files': 1,
                    'dll_excludes': ['MSVCP90.DLL', 'w9xpopen.exe'],
                    'compressed': True
                    },
            },
    version = VERSION,
    author = 'Samuel Barabas',
    windows = [{'script': 'TurtleUp.py'}],
    zipfile = None,
)

os.rename('dist/TurtleUp.exe', 'dist/TurtleUp_%s.exe' % VERSION)