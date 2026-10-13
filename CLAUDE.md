# Project notes for Claude Code sessions

Dubrovnik Workbench: a PC program (Tkinter / CustomTkinter) for the Dubrovnik SPI flash test board.
Current released version: 1.2. Read `README.md` (overview), `FOLDERS.md` (what each folder is for) and
`TODO_refactoring.md` (the code review and the planned refactoring) before changing code.

## Decisions already made (do not re-ask)

- **Versions:** never change the version, tag, build an installer or create a release unless the user says so.
  The next release that changes code is 1.2.1. A later release after the refactoring and removal of Classic may
  be called 2.0 (user's choice, decide then).
- **Git:** during the refactoring, commit after every green step (both test sets pass) and push the branch
  `refactor-app-class` right after (standing permission). Never push to `main`, never push tags, never amend or
  force-push pushed commits (fix forward or `git revert`). Outside the refactoring, commit and push only when asked.
  Never move or delete a pushed tag. Commit messages end with the Co-Authored-By line given by the harness.
- **Version during the refactoring:** `dubLibs/version.py` stays at 1.2.1 (already set, not tagged). Do not bump it
  per commit; tag `v1.2.1` only when the user says so.
- **Classic edition** was removed (first step of the refactoring). It lives on in tag `v1.2`; do not bring it back or
  add features for it. There is one program now: `dubGui/dubrovnik_workbench.py`.
- **Refactoring** is done on a separate branch (`refactor-app-class`), in small steps, one commit per step, and
  merged to `main` only when everything works and the user has tried it on a real board.
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
python -m unittest discover -s tests            unit tests, no windows, about 1 second (38 tests, 1 skipped on a clone)
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
  plain module name (`askopenfilename`, `showerror`) in `app.live` (= the module's `__dict__`). The panels reach
  the rest of the program through `self.app` (e.g. `self.app.serCom`, `self.app.term`).
- Menus are built by index (`insert_cascade(5, ...)`). Adding an item shifts the numbers below it.
- A window opened by the program takes the keyboard focus about 150 ms later: tests must `app.settle()` first.
- `tests/data` must stay byte-for-byte (`.gitattributes`); the sample files are used by tests.
- Edits made through shell here-documents have lost backslash escapes (`\n` in strings) more than once. Prefer the
  Edit tool or a script file, and compile (`python -I -m py_compile`) after each change.
- The help guide `help/dubrovnik_help.html` and `changelist.txt` must be updated with user-visible changes.
- Windows paths and PowerShell/Git Bash differ; the user's shell in VS Code is PowerShell, tools here may run Bash.

## Where things are

- `dubGui/` the program: `dubrovnik_workbench.py` (the `App` class, the panels, the Terminal; a compact launcher next
  to it), `look.py` (colours and widget styles) and `dialogs/` (one module per window: `messages`, `progress`,
  `hex_dialog`, `file_viewer`, `terminal_dialog`, `assistant_window`; each class is given what it needs, not the app).
  `dubLibs/` shared libraries without GUI code (`boardcom`, `dubrovnik`,
  `firmware_image`, `hexdump`, `run_py_script`, `cfgfile`, `termstyle`, `datasheet`, `assistant`)
- `tools/` Tools-menu scripts; `tests/` unit tests and `tests/data/`; `help/` the F1 guide; `docs/` Help > Documents.
