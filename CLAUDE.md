# Project notes for Claude Code sessions

Dubrovnik Workbench: a PC program (Tkinter / CustomTkinter) for the Dubrovnik SPI flash test board.
Latest tag: `v1.4.4` (on `main`, installer built locally, not published on GitHub; the last GitHub release is 1.4.3).
The next release will be **v1.5.0** (the user's decision: the SD card programming earns a minor bump); it is being
built on branch `program-sd-card` and `dubLibs/version.py` still says 1.4.4 until the user says to bump it. Read `README.md` (overview), `FOLDERS.md` (what each folder is for) and
`TODO_refactoring.md` (the code review and the planned refactoring) before changing code.

## Decisions already made (do not re-ask)

- **Versions:** never change the version, tag, build an installer or create a release unless the user says so.
  Version 1.3 was skipped on purpose: after 1.2.3 comes 1.4.0 (the Assistant, working, is planned as 1.5). A later release after the refactoring and removal of Classic may
  be called 2.0 (user's choice, decide then).
- **Git:** commit only when both test sets pass (check the exit code, not just the output). Add files by name or with
  `git add -u`, never `git add -A` (personal files lie around, e.g. in `tools/`). Never push to `main` or push tags
  without being asked. Never amend or force-push pushed commits (fix forward or `git revert`). Never move or delete
  a pushed tag. The branch `refactor-app-class` was pushed after every step (standing permission for that branch);
  for new work ask which branch to use (1.4.3 work went on branch `read-window-font-scaling`; small, clear changes
  were made straight on `main` when the user said so; still ask each time). Commit messages end with the
  Co-Authored-By line given by the harness.
- **Version:** `dubLibs/version.py` is 1.4.3, released on GitHub 2026-11-12 (commit a7bcf87, tag `v1.4.3`, installer
  `Dubrovnik-Setup-1.4.3.exe` attached). Also released on GitHub: 1.4.2 and 1.4.0. Tags `v1.4.0`, `v1.4.2`, `v1.4.3` are on
  origin (the commit b138e70 of `v1.4.2` is titled "V2.4.2" by mistake; never move the tag). 1.2.3 was released 2026-10-15
  (tag `v1.2.3`, installer only). Patch numbers (1.4.1, 1.4.2, 1.4.3) were used for bug-fix installers for the coworker;
  the next number is the user's choice (the Assistant, working, is planned as 1.5). Change the version, tag, build the
  installer and create a release only when the user says so. The tags `tested-on-board-1..8` mark commits the user tried
  on the real board.
- **Classic edition** was removed (first step of the refactoring). It lives on in tag `v1.2`; do not bring it back or
  add features for it. There is one program now: `dubGui/dubrovnik_workbench.py`.
- **Refactoring** (Classic removed, `App` class, dialogs and panels in their own modules, `Settings` object, menu
  tables) was done on branch `refactor-app-class` in small steps and merged into `main` after the user tried it on a
  real board. Same method for the next big change: a branch, one small step per commit, board test, then merge.
  The last two steps (panels with explicit arguments, long constructors split) were done on branch `refactor-finish`.
  What is left is only the optional list in `TODO_refactoring.md`.
- **Do not mix** structure changes and behaviour changes in one commit.
- **Audience:** only the author and one coworker use the program today, with about 50 internal boards. Wider
  release is planned for early next year. No need for deprecation notices, code signing or settings migration.
  The GitHub repository is private.
- **Quality gate is the real board.** Automated tests use a fake board. Ask the user to try on hardware before a
  merge or a release.
- **Personal folders** `dubScripts/`, `dubUtils/`, `packaging/` are not tracked (only the two README.txt files).
  Do not add their files to git. `packaging/` holds `build.bat`, `dubrovnik.spec`, `installer.iss`.

## Remind the user about version control (reminders only: never act without being asked)

The user is not a full-time software developer and does not always think of the housekeeping. Your job
is to **notice and say so, in one short line**; the decision stays theirs, and every rule above still
holds (no commit, push, version change, tag, build or release unless they say so).

Remind at natural checkpoints, not on every message: when a task or a feature is finished, before the
user switches to a different topic, when the user says "looks good" / "it works", and at the end of a
session. Say what is waiting and offer the next step, for example: "Uncommitted: the Terminal focus
change (3 files). Commit it?"

- **Uncommitted work:** commit finished, tested work in small steps, one topic per commit, with a message
  that says what and why. Remind when finished work sits uncommitted, or when one working copy holds more
  than one topic (offer to split it *before* it becomes one big commit). Untested or half-done work stays
  uncommitted or goes to a WIP branch. Never commit personal files (see Git above).
- **Unpushed commits:** remind that commits only on this PC are not backed up and not visible to anyone
  else. The user decides when to push; a feature branch may be pushed freely once asked.
- **Branch:** work on a feature branch, not on `main`. Remind when edits start while on `main`. `main`
  holds only what was board-tested; merge a branch after the user has tried it on the real board.
- **Docs travel with the change:** when a user-visible change is made, remind (or just do it, it is not a
  version-control action) that `help/dubrovnik_help.html` and `changelist.txt` need an entry in the same
  commit. Check that the tests were run (both sets) before suggesting a commit.
- **Version number:** the version changes once per release, in the release commit, together with the
  `changelist.txt` heading and the `README.md` line. Remind the user to decide the number when user-visible
  changes have piled up on `main`, or when they mention giving someone a build ("for the coworker", "for
  training"). Suggest the number by semantic versioning (bug fix: third number, new feature: second
  number, a break in how scripts or settings work: first number) and let them choose.
- **Release steps:** when the user says "release" or "new installer", walk the release recipe below and
  remind of what is still open: tests, merge to `main`, tag (after the merge, on the released commit),
  push the tag, build, release notes, GitHub release. Never move a tag that was pushed.
- **Backup of the unversioned work:** the personal folders (`dubScripts/`, `dubUtils/`, `packaging/`) are
  not in git. When the user changes something there that cannot be recreated (the installer script, the
  window checks, the golden menu file), remind them it exists only on this PC.
- **Do not nag:** if the user answers "not now", do not repeat the same reminder until the situation
  changes (more files, a new topic, the end of the session).

Why: git only protects what is committed and pushed, so a reminder turns "lost an afternoon's work" and
"which change broke it?" into a non-event. Small single-topic commits can be reviewed, reverted one by one
and bisected; a version number set once, at release, always matches the installer, the tag and the
change list, so a coworker's bug report ("version 1.4.3") points at exactly one commit.

## Commands (run from the project folder, C:\MyLibs\Dubrovnik)

```
python -m unittest discover -s tests            unit tests, no windows, about 1 second (about 114 tests)
python dubScripts\gui_tests\run_all.py          window checks, about 30 seconds (personal folder)
python dubScripts\gui_tests\check_menus.py wb   one check
python dubGui\dubrovnik_workbench.py            run the Workbench from source
packaging\build.bat                             build the installer (only when asked)
```

Run both test sets before and after every refactoring step. Use `.venv\Scripts\python.exe` if `python` is not
the project's. The window checks never touch the user's real settings (`%APPDATA%\Dubrovnik`); keep it that way.

## Things that are easy to get wrong here

- The program is a module with an `App` class (`App()` builds the window, `App().run()` starts the main loop). The
  test harness imports the module and builds an `App`: replace a method by assigning it on `app.workbench`, replace a
  plain module name (`askopenfilename`, `showerror`) in `app.live` (= the module's `__dict__`). The panels get what
  they need as constructor arguments (`serCom`, `term`, `du`, `settings`, ...); `App.buildPanels` wires them.
- Menus are tables in `dubGui/menus.py` (`File`, `View`, `Help`; Tools and Documents are filled when they open). Add or
  move an item there; find it in code by its key (`self.menus['view'].configure('panels', ...)`), never by number.
  An item is an `Item` (a command: the name of an `App` method), a `Radio` or a `Check` (both use a Tk variable held by `App`). After a menu change, run `check_menu_structure.py` and, if the change is
  meant, `python dubScripts\gui_tests\menu_dump.py --write` and read the difference of `menus_golden.json` (personal folder: not in git, so look at it before you write).
- A window opened by the program takes the keyboard focus about 150 ms later: tests must `app.settle()` first.
- `tests/data` must stay byte-for-byte (`.gitattributes`); the sample files are used by tests.
- Edits made through shell here-documents have lost backslash escapes (`\n` in strings) more than once. Prefer the
  Edit tool or a script file, and compile (`python -I -m py_compile`) after each change.
- The help guide `help/dubrovnik_help.html` and `changelist.txt` must be updated with user-visible changes.
- Windows paths and PowerShell/Git Bash differ; the user's shell in VS Code is PowerShell, tools here may run Bash.
- Files in the working copy use CRLF (autocrlf; git stores LF). The Edit tool keeps CRLF; a script that inserts text
  with plain newlines leaves mixed endings. Heredoc scripts lose backslashes: write script files with the Write tool.
- **Dialogs:** create with `look.newToplevel(root)` (hidden, takes the display scale of the main window, title bar
  coloured) and show once with `look.showCentered(win, root[, size=(w, h)])` (the size of a dialog that has a fixed
  `geometry()`). CustomTkinter's own title-bar hide-and-show is switched off on purpose (it flashed every dialog), so a
  light/dark change does not recolour an open dialog's title bar. A fixed-size dialog resizes itself after a change of
  display scale (`look.fitToContent`: Windows ignores the size CustomTkinter sets while the mouse is down).
  `dubScripts\gui_tests\manual_drag_dialog.py` drags a dialog between two displays with an injected mouse (manual).
- **Status register 2:** devices differ (on some, command 35 is "Read Sector Lockdown Registers"; 05 may or may not take a
  count). `Dubrovnik.status_forms()` asks the board's `help 35`, `5`, `31`, `1` once per connection (forgotten in
  `get_part_number` and `SerComFrame.deviceDetected`). The Read panel's `read_mode` sets or clears the Quad Enable bit
  before reading: kept as is on purpose (a warning or a Preference may come later). Commands typed in the Terminal go to
  the board unchanged (only trimmed, the `#` comment cut, `clear` is local).
- **One Documents folder:** `settings.documents_folder()` (asks Windows, OneDrive-aware) is used by the default script
  folders, Results and Assistant. Tests patch it; never let a check read the real `Documents\Dubrovnik`
  (`menu_dump.py` uses a temporary one).
- Flaky window checks (also on old code, on a busy PC): `check_threaded_programming` (slow-board pause limit 400 ms),
  `check_terminal_dialog`, `check_focus_keys` (needs real keyboard focus: Windows may refuse it while another window
  is in front or the user is typing). Run twice before calling it a regression.
- **SD card programming** (Tools > Program SD Card..., branch `program-sd-card`): `dubGui/dialogs/sd_wizard.py` (six
  pages with tick boxes) and `dubLibs/sd_card.py` (no GUI: a `Release` is a Teams zip (`20260918.zip` holding `20260918/boot_image.sb` and
  `relnotes.docx`, read from the zip), a folder or a bare .sb; releases live in `Documents\Dubrovnik\SD-card`; date from the
  `yyyymmdd` name, text of `relnotes.docx` with DOCTYPE/entities refused, copy as `boot_image.sb` via a temp file with a `.bak`, build
  date from the board's banner `Flash Memory Test Bench - Dec  5 2024 17:51:33`). NXP's MfgTool2.exe has no command
  line and its result cannot be read, so the user is asked whether the bar was green. The tool is not bundled
  (licence unknown, versioned folder names); its folder is a Configure Paths row (`mfgToolDir`). The board prints
  the banner by itself after RESET; the wizard reads it from the Terminal text after a mark (`endMark`/`textSince`).
- **GitHub:** `gh` is `C:\Program Files\GitHub CLI\gh.exe` (not on the Bash PATH); logged in as csabamoldvai. Release
  recipe: version in `dubLibs/version.py`, heading in `changelist.txt`, version line in `README.md`, run the unit tests
  and `run_all.py`, commit, push `main`, tag, push the tag, build with
  `cmd //c "C:\MyLibs\Dubrovnik\packaging\build.bat"` (full path; takes a few minutes, use a background run), notes in
  `packaging\release_notes_<version>.md`, then `gh release create v<version> <installer> --verify-tag --notes-file ...`.
  Each of these only when the user says so.

## Where things are

- `dubGui/` the program: `dubrovnik_workbench.py` (the `App` class: menus, actions, start-up; a compact launcher next
  to it), `look.py` (colours and widget styles), `menus.py` (the menus as tables), `panels/` (one module per panel: `serial_panel`, `erase_panel`,
  `program_panel`, `read_panel`, `terminal`, base class in `base`) and `dialogs/` (one module per window: `messages`,
  `progress`, `hex_dialog`, `file_viewer`, `terminal_dialog`, `assistant_window`, `assistant_settings`, `script_preview`, `sd_wizard`). Panels and dialogs get only what they
  need as arguments (no `self.app`).
  `dubLibs/` shared libraries without GUI code (`boardcom`, `dubrovnik`,
  `firmware_image`, `hexdump`, `run_py_script`, `cfgfile`, `termstyle`, `datasheet`, `assistant`, `assistant_config`, `fields`, `settings`, `sd_card`)
- Settings: one `dubLibs/settings.py` `Settings` object, made by `App` (`app.settings`) and given to whoever needs
  it (a constructor argument in the panels and the dialogs). It loads, validates and saves the
  file; `App.loadSettings` puts the entry-box values into the panels. `SerComFrame` only does the connection.
- Where files live (the author's PC now uses the same layout as the users): program folder (`dubGui`, `dubLibs`, `tools\`
  shared Tools menu entries, `docs\`, `help\`; installed: the PyInstaller bundle); `%APPDATA%\Dubrovnik` (settings
  `dubrovnik_workbench.cfg`, `assistant.cfg`, `Datasheets\`, the old Classic `dubrovnik.cfg` read once);
  `Documents\Dubrovnik\` `commandScripts`, `pythonScripts`, `myTools` (the user's Tools menu entries: a script whose
  first line is `# TOOL: name`; `.txt`/`.scr` first line only, `.py` within 20 lines), `Results`, `Assistant`.
  `dubScripts\` now only has `gui_tests`, `legacy`, `scratch`.
- Ideas not done: a warning or Preference for the Quad Enable step of Read; rename the Configure Paths row "Documents"
  (it is the program's `docs\`) to "Help documents"; put datasheets in `Documents\Dubrovnik\Datasheets` (decided not to
  for now: OneDrive sync of confidential PDFs, network Documents); keep an eye on the CustomTkinter icon that pops into
  a dialog's title bar about 200 ms after it opens.
- `tools/` Tools-menu scripts; `tests/` unit tests and `tests/data/`; `help/` the F1 guide and `assistant_reference.md` (for the AI Assistant, not wired in yet); `docs/` Help > Documents.
