# TODO: refactoring and design lessons

**Written for version 1.2** (commit `7bf6a87` on `main`, 2026-10-12). Status on branch `refactor-app-class`: Classic removed (item 5 below), the main block moved into an `App` class
(item 1 below), the big dialogs moved into `dubGui/dialogs/` (item 2), the settings made an object
(`dubLibs/settings.py`, item 3) and the panels moved into `dubGui/panels/`. The menus became tables (`dubGui/menus.py`, item 4). The workbench file went from 2,861 to about 1,000 lines.
The last two steps are done too (branch `refactor-finish`): the panels get explicit arguments instead of `self.app`, and the
long constructors of `App` (229 lines to 18), `TerminalDialog` (179 to 20), `HexDialog` and the Assistant windows are split into methods.
Nothing is open that matters; what is left is optional: the longest functions are now `programFile` (76), `ReadFrame.buildFrame` (63)
and `App.buildPanels` (63).
The numbers below describe the code as it was at that version; the commands in
[How to measure again](#how-to-measure-again) let you compare later.

Purpose of this file: a record of an honest review of the Workbench code, to read again in the future,
both to decide *when and how* to refactor and to **design the next program with these lessons in mind**.
It is not a to-do for the next release: the program works, is tested and is shipping.

---

## 1. The question that started this

*Is it typical for a GUI of this complexity (`dubGui/dubrovnik_workbench.py`) to have so many lines? Is the code
well structured? Does it need refactoring?*

### Size, measured at version 1.2

| What | Lines |
|---|---|
| `dubGui/dubrovnik_workbench.py` (Workbench) | 2,861 |
| `dubGui/dubrovnik_workbench_classic.py` (Classic edition) | 2,347 |
| All of `dubLibs/` (board communication, file readers, hex dump, scripts, settings validation) | about 2,300 |
| Of the Workbench: the block under `if __name__ == "__main__":` | 1,403 (49 %) |
| Functions defined *inside* that block | 48 |
| Module-level classes and functions above the block | 18 |
| Longest functions | `showTerminalDialog` about 185-205, `showAssistant` about 95, `showHexDialog` about 80, `programFile` about 75 |
| Lines of the Workbench that also appear word for word in Classic | 840 of 1,425 (59 %) |

### Is this size typical?

Yes. A Tkinter application with this many features (panels, menus, dialogs, a terminal, settings, scripting)
commonly reaches 2,000 to 4,000 lines in one file. **Line count is a weak signal.** What matters is whether the
parts are cohesive (each does one thing) and how tightly they depend on each other (coupling).

---

## 2. What is well structured (keep this)

- **Logic is separated from windows.** About 2,300 lines in `dubLibs` do the real work (talk to the board, read
  `.bin` / S-record / Intel HEX, format the hex dump, run scripts, validate settings) with **no GUI code**. They can be
  tested without opening a window. This is the most valuable separation, and it already exists.
- **Panels are classes** (`EraseFrame`, `ProgramFrame`, `ReadFrame`, `Terminal`) with a shared base (`LabeledFrame`).
- **Settings validation lives in a library** (`cfgfile.py`, `termstyle.py`), not scattered through the windows.
- **Tests exist** at two levels: unit tests in `tests/` for the libraries, and window-level checks in
  `dubScripts/gui_tests/` (personal folder, see `FOLDERS.md`).
- **Long work runs in a thread** and talks back through a queue and a timer, so the window stays responsive.
- **Folders have a documented purpose** (`FOLDERS.md`).

## 3. What is not (the weak spots)

1. **A 1,400-line `if __name__ == "__main__":` block holds half the file.**
   It contains 48 nested functions: menu actions, dialogs, Run Script, Run Tool, the Firmware actions, and so on.
   They share state through variables such as `root`, `serCom`, `term` and `program`, which the classes above the
   block also reach for. In effect these are **globals**.
   Consequences: the file cannot be imported without running the program; the test harness needs the trick
   `program.openFile.__globals__` to replace anything the program calls; and there is no clear place where "the
   application" begins.
2. **Hidden coupling.**
   - The panel classes read module-level objects instead of receiving them.
   - `SerComFrame` (a connection panel) also saves and loads settings for the *whole* application and knows about the
     Erase, Program and Read panels' variables.
   - `get_states` uses `global` statements.
3. **Long functions that mix layout, behaviour and clean-up** (the dialogs above). Hard to read, hard to test.
4. **Menus are built by position.** For example `file_menu.insert_cascade(5, ...)`: adding an item above silently
   shifts every number below it. This had to be corrected several times.
5. **Duplication between the two editions.** About 59 % of the longer lines are identical in Workbench and Classic.
   Every feature (Hex Dump, Firmware menu, Terminal dialog, viewer) had to be written twice, and tested twice.
6. **A note on my own contribution:** the dialogs and viewers added in versions 1.1.2 to 1.2 were put inside the
   main block, following the existing pattern. That made the block bigger. Separate modules would have been cleaner.
   Following an existing pattern is not the same as following a good one.

---

## 4. Does it need refactoring?

**Not urgently.** It works, ships and has tests. Refactoring costs time and risks breaking behaviour that nobody
remembers writing. Do it when the structure starts to slow you down:

- you cannot find where something happens,
- a change in one place breaks something far away,
- a coworker cannot add a feature without reading the whole file,
- a bug fix has to be copied to Classic and gets forgotten,
- you want to test something and have to start the whole program to do it.

### Suggested order (smallest and safest first)

1. **Move the main block into a function or an `App` class.** Mostly mechanical: the nested functions become methods
   and the shared objects become attributes (`self.root`, `self.settings`, ...). Gains: the program becomes importable,
   tests need no `runpy` tricks, and there is one clear entry point.
2. **Move the big dialogs into their own modules** (Terminal dialog, Hex Dump dialog, File viewer, progress window,
   Assistant). Each becomes a class that is given what it needs (settings, a callback) and returns a result.
3. **Give the settings their own object** (loaded once, passed to whoever needs it) instead of attributes of
   `SerComFrame`. A small class or a `dataclass` with defaults, validation, `load()` and `save()`.
4. **Table-driven menus:** describe each menu as a list of `(key, label, shortcut, command)` and find entries by
   key, not by index.
5. **A shared core for both editions.** The biggest saving and the biggest job, because the two use different widget
   sets (CustomTkinter and plain tkinter). The simpler question to ask first: *is Classic still needed?* It was not: removed, see the status line at the top.

### How to refactor safely

- **Tests first.** Run the unit tests (`python -m unittest discover -s tests`) and the window checks
  (`python dubScripts\gui_tests\run_all.py`) before you start and after every step.
- **One move at a time, one commit per move.** If something breaks, the last small commit is the suspect.
- **Do not split by line count.** Cutting a file into 500-line pieces spreads the same coupling over more files.
- **Do not rewrite from scratch.** A rewrite loses behaviour that nobody wrote down.
- **Change structure or behaviour, never both in the same commit.**

---

## 5. Design lessons for the next program

If you start a new program, build these in from the first day. They are cheap at the start and expensive later.

1. **Nothing at module level except imports and definitions.** The end of the file is `main()`; `main()` creates an
   `App` object and runs it. No logic in an `if __name__` block.
2. **Pass dependencies in; do not reach for globals.** A panel receives the settings and the board connection in its
   constructor. Then it can be tested and reused, and it is obvious what it depends on.
3. **Keep the logic free of the GUI.** Anything that is not "draw this" or "react to a click" goes into a library
   module that does not import tkinter. Test it with unit tests. The GUI becomes a thin layer on top.
4. **One module per window or dialog.** A dialog is a class with a `show()` method that returns what the user chose.
   Keep each under about 100 lines.
5. **Settings are one object** with defaults, validation, `load()` and `save()`, created in one place and passed
   around. Never scatter `open(...)` of the settings file through the code.
6. **Declare menus as data**, not as a series of `add_command` calls with index numbers. Refer to items by name.
7. **Keep functions short** (a rule of thumb: about 50 lines). If a function needs a comment to separate its parts,
   those parts are functions.
8. **Hide the hardware behind a small interface** (`send`, `read`, ...). Then a fake can stand in for it, in tests
   and in demos, with no changes to the program. We got this right with `FakeComm`; do it deliberately next time.
9. **Make the app testable without its main loop.** Design a way to build all windows and then drive them (see
   `dubScripts/gui_tests/harness.py`): settings location configurable, dialogs replaceable, no code that insists on
   running forever.
10. **Do the long work off the GUI thread from the start** (a worker thread plus a queue and a timer), and let Cancel
    and errors be part of the design, not an afterthought.
11. **Avoid two versions of the same program.** If two editions are needed, put the shared behaviour in a core and
    let the editions differ only in how they draw. Otherwise every feature is written, fixed and tested twice.
12. **Decide the folder layout and write it down early** (`FOLDERS.md`), including what is shared and what is personal.
13. **Write down decisions as you make them** (this file is an example): the why is the first thing to be forgotten.

### Warning signs to watch for

- A function you scroll through. A file you cannot hold in your head.
- `global` anywhere.
- Index numbers in code that refer to positions (menu items, columns, list slots).
- The same block of code copied into a second file.
- A test that needs the whole program running to check one rule.
- "I'll tidy it later", repeated.

### The idea to take away

Judge code by **how many things you must keep in mind to change one part**. A big file can be fine if it is organised,
and many small files can be a mess if everything depends on everything. In this project the libraries are good; the weak
spot is the large main block that holds the application together.

---

## How to measure again

Run these from the project folder to compare with the table in section 1 (Git Bash / any shell with `grep`, `awk`;
the Python part works anywhere).

```
wc -l dubGui/dubrovnik_workbench.py dubGui/*.py dubGui/panels/*.py dubGui/dialogs/*.py dubLibs/*.py
```

```python
# the longest functions of the program (all of dubGui)
import ast, glob
funcs = []
for path in glob.glob('dubGui/**/*.py', recursive=True):
    for n in ast.walk(ast.parse(open(path, encoding='utf-8').read())):
        if isinstance(n, ast.FunctionDef):
            funcs.append((n.end_lineno - n.lineno + 1, path, n.name))
print(sorted(funcs, reverse=True)[:8])
```

If the files get shorter, the longest function gets shorter and the panels and dialogs stay free of `self.app`, the
refactoring is working.
