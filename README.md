# Dubrovnik Workbench

PC application for the **Dubrovnik** flash test board. It erases, programs and reads SPI flash devices in the
board's socket, and gives you a terminal, scripts and ready-made tools for talking to the board's
**Tiberias** firmware.

Current version: **1.2.3** (see [changelist.txt](changelist.txt)).

## Features

- **Erase, Program, Read** panels for the flash in the socket. Read supports SPI, Dual, Quad (1-1-4) and
  Quad (1-4-4); the Quad Enable bit is handled automatically.
- **Firmware files** (File > Firmware): open a `.bin`, Motorola S-record (`.srec`, `.s19`, `.mot` ...) or Intel HEX
  file, preview it, view all of it as a hex dump, and program it block by block at its own addresses plus an Offset,
  with a progress window and Cancel. It works also with the panels hidden.
- **Hex Dump** display mode for Read (address, hex bytes, ASCII, like a hex editor) with its own settings
  (View > Hex Dump).
- **Terminal** for any Tiberias command (`volt`, `freq`, `config`, flash opcodes, ...). It works without a
  flash device in the socket. Command history, read-only history area, save the log to a file.
- **Scripts** (File > Scripts): run a text file of Terminal commands, or a Python script that uses the
  built-in `dub` object (`dub.send`, `erase`, `program`, `read`, `read_bytes`, `hexdump`, `load_image`,
  `program_image`, `verify`, dialogs, result files, ...). Esc stops them. A command script is listed first with line numbers (Run / Cancel), `#` comments in it are
  shown as it runs, and both can be switched off in File > Scripts. The Terminal command line accepts `# comments` too.
- **Tools menu** built from the scripts in the [tools](tools) folder: Functional Test, SFDP Program (ATXP032),
  Icc Read Measurement and INA230 Calibration. A new tool is a Python file, or a command script (`.txt`/`.scr`), with a `# TOOL: name` header (the first line for a command script).
- Remembers window size and position, panels, theme, COM port and display mode. The Erase/Program/Read entry
  values are saved only when you choose File > Parameters > Save.
- Terminal look (View > Terminal): theme, colours, font and size, and Ctrl + mouse wheel zoom. Menu text size and a
  one-click Hide/Show Panels item in the View menu.
- Help > Datasheet opens the datasheet of the device in the socket (a file in `docs`, or a web search).
- Notices when the board is switched off or unplugged.
- Built-in user guide: Help > Help (F1), source in [help/dubrovnik_help.html](help/dubrovnik_help.html).
  It covers the panels, Terminal command rules, power measurement, probing signals and a glossary.
- Help > Documents lists the files in the `docs` folder (board schematic, the searchable Dubrovnik Training Guide,
  and anything else you drop there).

## The program

**Dubrovnik Workbench**, `DubrovnikWorkbench.exe`, source [dubGui/dubrovnik_workbench.py](dubGui/dubrovnik_workbench.py)
(CustomTkinter, light/dark appearance). It uses the libraries in [dubLibs](dubLibs), the tools and the help.

The older Classic edition (plain tkinter) was discontinued after version 1.2. It stays available in the `v1.2` tag
and in the 1.2 installer.

`dubGui/dubrovnik_workbench_compact.py` starts the Workbench with everything about 12 % smaller.

## Install

Run `Dubrovnik-Setup-<version>.exe`. It installs the program for the current user (no administrator
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
python dubGui\dubrovnik_workbench.py
```

## Quick start

1. Connect the board with the USB cable and switch it on.
2. Start the program and click **Connect** (or tick *Auto connect*).
3. Insert the flash device and press the board's **RESET** button.
4. Use the Erase, Program and Read panels; results and timings appear in the Terminal.

## Settings

Stored in `%APPDATA%\Dubrovnik`: `dubrovnik_workbench.cfg`. A damaged
file is replaced by defaults and kept with `.bad` added to its name. The uninstaller asks whether to delete
this folder.

## Project layout

```
dubGui/      the applications
dubLibs/     board communication, flash functions, settings, script runners, version number
tools/       scripts shown in the Tools menu
help/        user guide (HTML)
docs/        documents shown in Help > Documents (schematic, training guide, how it works)
changelist.txt, TODO List Dubrovnik.txt, requirements.txt, requirements-dev.txt
```

What is in each folder:

| Folder | Contents | In git |
|---|---|---|
| `dubGui/` | The program (the Workbench) | yes |
| `dubLibs/` | Shared libraries: board communication, firmware file reader, hex dump, script support | yes |
| `tools/` | Scripts of the Tools menu (a `# TOOL:` header makes an entry) | yes |
| `help/`, `docs/` | The built-in user guide; documents of the Help > Documents menu | yes |
| `tests/` | Unit tests (`python -m unittest discover -s tests`); `tests/data/` holds the sample firmware images and dumps | yes |
| `dubScripts/` | Your own command and Python scripts and examples (`legacy/` holds old scripts) | no |
| `dubUtils/` | Small stand-alone utilities, e.g. `text2bin_file.py` | no |
| `packaging/` | Installer build | no |

The folders marked "no" are kept locally and not tracked by git (see `.gitignore`). See [FOLDERS.md](FOLDERS.md) for the full folder guide and how we share scripts and data.

## Versions and releases

The version number is set in one place, [dubLibs/version.py](dubLibs/version.py); the About dialogs, the help
file, the installer and the file properties of the `.exe` files read it from there.

**Numbering.** `1.2` is a feature release (new things people will notice), `1.2.1` a fix release. Earlier
feature releases are tagged `v1.0`, `v1.1`, `v1.2`; fix releases `v1.1.3` and so on. The tag is always the
version with a `v` in front.

### Release checklist

1. **Test.** `python -m unittest discover -s tests` must pass. Run the program from source and try the new
   features, on the board if you can (the tests use a fake board).
2. **Set the version.** Change `VERSION` in `dubLibs/version.py` (for example `'1.2'`) and the
   "Current version" line at the top of this README.
3. **Write the change list.** Add an entry at the top of `changelist.txt`, above the previous version, with
   the same heading layout (`VERSION 1.2   <date>`, a line of dashes, a short summary, then "New:",
   "Changed:" and "Fixed:" lists).
4. **Check the help guide** (`help/dubrovnik_help.html`): new menu items, settings and script calls are
   described, and nothing refers to things that were removed.
5. **Build the installer.** Run `packaging\build.bat`. It creates
   `packaging\installer\Dubrovnik-Setup-<version>.exe`. Start the program from `packaging\dist\Dubrovnik`
   once to see that it opens, and check the version in the title bar.
6. **Commit and tag.**
   ```
   git add -A README.md changelist.txt dubGui dubLibs help tests
   git commit -m "Version 1.2: <one line summary>"
   git tag -a v1.2 -m "Version 1.2"
   git push origin main
   git push origin v1.2
   ```
   Run `git status` first: personal files (`dubScripts/`, `dubUtils/`, `packaging/`) must not be added.
7. **Write the release notes** for GitHub (see the template below) and save them as
   `packaging\release_notes_<version>.md` next to the installer, so the text is kept.
8. **Publish the release** on GitHub (next section).

### Publishing the release on GitHub

A GitHub release is the download page for a version. The tag from step 6 must already be pushed.

1. Open the repository on GitHub, then **Releases** (right side of the main page) and **Draft a new release**
   (or go to `https://github.com/csabamoldvai/Dubrovnik/releases/new`).
2. Fill in the form:

| Field | What to enter |
|---|---|
| **Choose a tag** | Pick the existing tag, for example **v1.2**. Do not create a new one here; this field must match the tag you pushed. |
| **Target** | Not shown for an existing tag (it is the tagged commit). |
| **Previous tag** (only used by "Generate release notes") | Leave on *auto*. We write the notes ourselves. |
| **Release title** | `Dubrovnik Workbench 1.2` (product name and version, no `v`). |
| **Description** | Open `packaging\release_notes_1.2.md` in a text editor, select all, copy, and paste it here. GitHub shows the formatting in the **Preview** tab. Do not paste `changelist.txt`: it is long and written for developers. |
| **Attach binaries** | Drag `packaging\installer\Dubrovnik-Setup-1.2.exe` onto the box at the bottom, or click it to browse. Wait until the file name appears with its size. Do not attach the `dist` folder; the installer contains everything. GitHub adds the source code (zip and tar.gz) by itself. |
| **Set as a pre-release** | Tick it if this version has not been tried on a real board. Leave it unticked for a normal release. |
| **Set as the latest release** | Leave ticked for a normal release. |
| **Create a discussion for this release** | Leave unticked. |

3. Click **Publish release** (or **Save draft** to look at it first). A published release can be edited
   later with the pencil icon, so a typo in the notes is easy to fix.
4. Check it: open the release page, download the installer, and compare its size with
   `packaging\installer`. The installer is not code-signed, so Windows SmartScreen may show "More info" /
   "Run anyway"; the release notes say so.

**With the GitHub command-line tool** (`gh`, after `gh auth login`) the same release is one command:

```
gh release create v1.2 packaging\installer\Dubrovnik-Setup-1.2.exe --title "Dubrovnik Workbench 1.2" --notes-file packaging\release_notes_1.2.md
```

Add `--prerelease` for a pre-release.

**Release notes template** (`packaging\release_notes_<version>.md`; the 1.0, 1.1 and 1.2 files are examples):

```
## Dubrovnik Workbench <version>

One or two sentences: what this version is about, and "Installs over <previous> and keeps your settings."

### New
- **Feature name:** what it does for the user, in one or two lines.

### Changed
- Behaviour that is different from before.

### Fixed
- Problems that are gone (leave this section out if there are none).

### Install
Download `Dubrovnik-Setup-<version>.exe` and run it. No admin rights are needed. The installer is not
code-signed, so Windows SmartScreen may ask you to confirm ("More info" > "Run anyway"). Details are in
`changelist.txt`.
```

Write for the people who install the program, not for developers: user-visible features first, no file names
of source code, short sentences.

**If something is wrong after publishing.** A wrong description or file: edit the release and replace the
file. A wrong tag (the tag points at the wrong commit): delete the release and the tag
(`git tag -d v1.2` and `git push origin :refs/tags/v1.2`), fix the problem, and start again from step 6.
Do not move a tag that other people may already have downloaded; make a new fix release (`1.2.1`) instead.

## Building the installer

`packaging\build.bat` builds the program with PyInstaller (`pip install -r requirements-dev.txt`) and
compiles the installer with Inno Setup 6 or 7. Output: `packaging\installer\Dubrovnik-Setup-<version>.exe`.
The `packaging` folder is not currently tracked in git.

## Status

Version 1.0 was developed and tested against a simulated board. Please check the first runs on real hardware,
especially Dual/Quad reads and the Tools scripts, which can erase or reprogram the device and change board
settings. Known gaps: Prog/Verify, QPI/Octal reads, VT distribution tool. See the TODO list.

## Authors

Csaba Moldvai (system/board design, GUI) and Eyal Barzilay (Tiberias flash support software).
