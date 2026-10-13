dubScripts - YOUR scripts for the Dubrovnik board
=================================================

What goes here
  Command scripts (.txt) and Python scripts (.py) that you run from the
  Workbench with File > Scripts. The Run Script dialog starts in this folder.

Personal, not shared
  This folder is not tracked by git (see .gitignore); only this README is.
  Your files stay on your PC: they are not backed up by git and not in the
  installer. Back them up yourself (OneDrive or a copy) if they matter.

Sub-folders
  legacy\   old scripts, kept for reference. They may not run any more.

Sharing a script with the team
  1. Try it until it works on a board.
  2. Copy it to the tools\ folder.
  3. Add this header at the top of the file (see dubLibs\tools.py):
         # TOOL: Name shown in the Tools menu
         # DESCRIPTION: one line shown in the status bar
         # CONFIRM: question the user must answer Yes to
  4. Commit it. It then shows up in the Tools menu of everybody.

Rules of thumb
  - Write result files with dub.output_path("name.txt"); they end up in
    Documents\Dubrovnik\Results.
  - Use dub.sleep(), not time.sleep(), so the window stays alive and Esc works.
  - Calls you can use: dub.send, erase, program, read, read_bytes, hexdump,
    load_image, program_image, verify, ask, confirm, message, output_path.
    See the Scripts section of the built-in help (F1).

More about all folders: FOLDERS.md in the project root.
