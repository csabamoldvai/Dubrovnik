dubUtils - YOUR small stand-alone PC utilities
==============================================

What goes here
  Small programs you run from a terminal that only process files on the PC:
  convert, extract, compare. They do not need the board and do not use the
  "dub" object. Example: text2bin_file.py (text file to binary file).

  If it needs the board, it is a script: use dubScripts\ (yours) or tools\
  (shared) instead.

Personal, not shared
  This folder is not tracked by git (see .gitignore); only this README is.
  Your files stay on your PC and are not in the installer.

Habits that help
  - Take file names as command-line arguments; do not hard-code folders.
  - Start the file with a short docstring that says what it does and how to run it.
  - Put sample data in tests\data\, not here.
  - If a utility becomes useful for the whole team, tell the owner of the project;
    it can move into a shared folder with a test.

More about all folders: FOLDERS.md in the project root.
