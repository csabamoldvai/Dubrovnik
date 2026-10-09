# Dubrovnik Workbench

PC application for the **Dubrovnik** flash test board. It erases, programs and reads SPI flash devices in the
board's socket, and gives you a terminal, scripts and ready-made tools for talking to the board's
**Tiberias** firmware.

Current version: **1.1** (see [changelist.txt](changelist.txt)).

## Features

- **Erase, Program, Read** panels for the flash in the socket. Read supports SPI, Dual, Quad (1-1-4) and
  Quad (1-4-4); the Quad Enable bit is handled automatically.
- **Terminal** for any Tiberias command (`volt`, `freq`, `config`, flash opcodes, ...). It works without a
  flash device in the socket. Command history, read-only history area, save the log to a file.
- **Scripts** (File > Scripts): run a text file of Terminal commands, or a Python script that uses the
  built-in `dub` object (`dub.send`, `erase`, `program`, `read`, dialogs, result files, ...). Esc stops them.
- **Tools menu** built from the scripts in the [tools](tools) folder: Functional Test, SFDP Program (ATXP032),
  Icc Read Measurement and INA230 Calibration. A new tool is a Python file with a `# TOOL: name` header.
- Remembers window size and position, panels, theme, COM port and display mode. The Erase/Program/Read entry
  values are saved only when you choose File > Parameters > Save.
- Notices when the board is switched off or unplugged.
- Built-in user guide: Help > Help (F1), source in [help/dubrovnik_help.html](help/dubrovnik_help.html).
  It covers the panels, Terminal command rules, power measurement, probing signals and a glossary.
- Help > Documents lists the files in the `docs` folder (board schematic, the searchable Dubrovnik Training Guide,
  and anything else you drop there).

## Two editions

| Edition | Program | Source |
|---|---|---|
| **Dubrovnik Workbench** | `DubrovnikWorkbench.exe` | [dubGui/dubrovnik_workbench.py](dubGui/dubrovnik_workbench.py) (CustomTkinter, light/dark appearance) |
| **Dubrovnik Workbench (Classic)** | `DubrovnikClassic.exe` | [dubGui/dubrovnik_workbench_classic.py](dubGui/dubrovnik_workbench_classic.py) (the original look, tkinter) |

They share the libraries in [dubLibs](dubLibs), the tools and the help. Each keeps its own settings file.
`dubGui/dubrovnik_workbench_compact.py` starts the Workbench with everything about 12 % smaller.

## Install

Run `Dubrovnik-Setup-<version>.exe`. It installs both editions for the current user (no administrator
rights) and adds Start-menu entries; desktop shortcuts are optional. No Python is needed.

Requirements: Windows 10 or 11 (64-bit) and the USB driver of the board's FTDI serial chip, which Windows
normally installs by itself. The installer is not code-signed, so Windows SmartScreen may ask you to confirm
("More info" > "Run anyway").

## Run from source

Python 3.12 on Windows:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python dubGui\dubrovnik_workbench.py          # Workbench
python dubGui\dubrovnik_workbench_classic.py  # Classic edition
```

## Quick start

1. Connect the board with the USB cable and switch it on.
2. Start the program and click **Connect** (or tick *Auto connect*).
3. Insert the flash device and press the board's **RESET** button.
4. Use the Erase, Program and Read panels; results and timings appear in the Terminal.

## Settings

Stored in `%APPDATA%\Dubrovnik`: `dubrovnik_workbench.cfg` (Workbench) and `dubrovnik.cfg` (Classic). A damaged
file is replaced by defaults and kept with `.bad` added to its name. The uninstaller asks whether to delete
this folder.

## Project layout

```
dubGui/      the applications
dubLibs/     board communication, flash functions, settings, script runners, version number
tools/       scripts shown in the Tools menu
help/        user guide (HTML)
docs/        documents shown in Help > Documents (kept locally, not tracked)
changelist.txt, TODO List Dubrovnik.txt, requirements.txt, requirements-dev.txt
```

Folders kept locally and not tracked by git (see `.gitignore`): `dubScripts/` (example and personal scripts),
`dubUtils/` (older utilities such as `.srec` handling), `packaging/` (installer build), `docs/` (internal
documents such as the schematic and the training guide).

## Versions and releases

The version number is set in one place, [dubLibs/version.py](dubLibs/version.py); the About dialogs, the help
file and the installer read it from there. To release: change `VERSION`, add an entry at the top of
`changelist.txt`, commit, and tag the commit (`git tag -a v1.1 -m "Version 1.1"`).

## Building the installer

`packaging\build.bat` builds both programs with PyInstaller (`pip install -r requirements-dev.txt`) and
compiles the installer with Inno Setup 6 or 7. Output: `packaging\installer\Dubrovnik-Setup-<version>.exe`.
The `packaging` folder is not currently tracked in git.

## Status

Version 1.0 was developed and tested against a simulated board. Please check the first runs on real hardware,
especially Dual/Quad reads and the Tools scripts, which can erase or reprogram the device and change board
settings. Known gaps: Prog/Verify, QPI/Octal reads, VT distribution tool. See the TODO list.

## Authors

Csaba Moldvai (system/board design, GUI) and Eyal Barzilay (Tiberias flash support software).
