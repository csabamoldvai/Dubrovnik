# Project notes for Claude Code sessions

Dubrovnik Workbench: a PC program (Tkinter / CustomTkinter) for the Dubrovnik SPI flash test board.
Current released version: 1.2. Read `README.md` (overview), `FOLDERS.md` (what each folder is for) and
`TODO_refactoring.md` (the code review and the planned refactoring) before changing code.

## Decisions already made (do not re-ask)

- **Versions:** never change the version, tag, build an installer or create a release unless the user says so.
  The next release that changes code is 1.2.3 (1.2.2 is released and tagged). A later release after the refactoring and removal of Classic may
  be called 2.0 (user's choice, decide then).
- **Git:** commit only when both test sets pass (check the exit code, not just the output). Add files by name or with
  `git add -u`, never `git add -A` (personal files lie around, e.g. in `tools/`). Never push to `main` or push tags
  without being asked. Never amend or force-push pushed commits (fix forward or `git revert`). Never move or delete
  a pushed tag. The branch `refactor-app-class` was pushed after every step (standing permission for that branch);
  for new work ask which branch to use. Commit messages end with the Co-Authored-By line given by the harness.
- **Version:** `dubLibs/version.py` is 1.2.2, released 2026-10-14 (tag `v1.2.2`). The next release will be 1.2.3 or larger; change the version, tag and build the installer only when the user says so. The tags `tested-on-board-1..5` mark commits the user tried on the real board.
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

## Commands (run from the project folder, C:\MyLibs\Dubrovnik)

```
python -m unittest discover -s tests            unit tests, no windows, about 1 second (63 tests, 1 skipped on a clone)
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

## Where things are

- `dubGui/` the program: `dubrovnik_workbench.py` (the `App` class: menus, actions, start-up; a compact launcher next
  to it), `look.py` (colours and widget styles), `menus.py` (the menus as tables), `panels/` (one module per panel: `serial_panel`, `erase_panel`,
  `program_panel`, `read_panel`, `terminal`, base class in `base`) and `dialogs/` (one module per window: `messages`,
  `progress`, `hex_dialog`, `file_viewer`, `terminal_dialog`, `assistant_window`, `assistant_settings`, `script_preview`). Panels and dialogs get only what they
  need as arguments (no `self.app`).
  `dubLibs/` shared libraries without GUI code (`boardcom`, `dubrovnik`,
  `firmware_image`, `hexdump`, `run_py_script`, `cfgfile`, `termstyle`, `datasheet`, `assistant`, `assistant_config`, `fields`, `settings`)
- Settings: one `dubLibs/settings.py` `Settings` object, made by `App` (`app.settings`) and given to whoever needs
  it (a constructor argument in the panels and the dialogs). It loads, validates and saves the
  file; `App.loadSettings` puts the entry-box values into the panels. `SerComFrame` only does the connection.
- `tools/` Tools-menu scripts; `tests/` unit tests and `tests/data/`; `help/` the F1 guide; `docs/` Help > Documents.
