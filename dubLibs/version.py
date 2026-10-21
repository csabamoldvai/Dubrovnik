"""Single source of truth for the version number of the Dubrovnik apps.

To release a new version:
  1. change VERSION below,
  2. add an entry at the top of changelist.txt,
  3. commit and tag it:  git tag v<VERSION>
The About dialogs, the help file and the installer all read it from here.
"""
VERSION = '1.4.0'

if __name__ == '__main__':      # used by packaging\build.bat
    print(VERSION)
