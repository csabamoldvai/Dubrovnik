# Folder guide

What each folder of the Dubrovnik project is for, and how we share code and data.
Read this first when you set up the project on a new PC or want to add something.

## The layout

```
Dubrovnik/
├── dubGui/        the two programs: Workbench and Classic              (shared)
├── dubLibs/       libraries used by both programs and by scripts       (shared)
├── tools/         ready-made procedures shown in the Tools menu        (shared)
├── help/          the built-in user guide (F1)                         (shared)
├── docs/          documents of the Help > Documents menu               (shared)
├── tests/         unit tests                                           (shared)
│   └── data/        sample firmware images and dumps used by the tests (shared)
├── dubScripts/    YOUR command and Python scripts                      (personal)
│   └── legacy/      old scripts kept for reference
├── dubUtils/      YOUR small stand-alone PC utilities                  (personal)
├── packaging/     installer build (PyInstaller + Inno Setup)           (personal)
├── README.md      what the program does, install and run
├── changelist.txt what changed in each version
└── FOLDERS.md     this file
```

**Shared** folders are tracked in git: everybody has the same content. **Personal** folders
are listed in `.gitignore`; only their `README.txt` is tracked, so the folder exists on
every PC and explains itself, while the files you put in it stay on your PC.

## What goes where

| You have | Put it in | Why |
|---|---|---|
| A command script (`.txt`) or Python script for the board that is yours or still in progress | `dubScripts/` | Run it with File > Scripts. Private, nothing to review. |
| A script that others should use too | `tools/` | Tracked, bundled in the installer, and a `# TOOL: name` line at the top makes it appear in the Tools menu. |
| A small program that only processes files on the PC (convert, extract, compare), no board needed | `dubUtils/` | Not run from the Workbench, so it is not a script. |
| A sample firmware image or dump that a test uses | `tests/data/` | Tracked, so tests work on every PC. |
| A script's result files (logs, measurements) | `Documents\Dubrovnik\Results` | Use `dub.output_path("name.txt")` in the script. Never commit result files. |
| A datasheet or other reference document | `docs/` | Appears in Help > Documents. Do not put confidential documents here: they are bundled in the installer. |
| Code that several scripts or both programs need | `dubLibs/` | Add a test in `tests/` for it. |

A quick test for **script or utility?**: if it needs the board, it is a script (`dubScripts`
or `tools`); if it only works on files, it is a utility (`dubUtils`).

## Sharing

- **Sharing a script:** copy it from `dubScripts/` to `tools/`, add the `# TOOL:` header (see
  `dubLibs/tools.py`), try it, and commit it. Start from `tools/functional_test.py`.
- **Sharing data:** put the file in `tests/data/` and add a test that uses it. Keep files small
  (the largest sample is about 300 KB).
- **Do not commit** personal files, result files, or anything confidential. Check
  `git status` before you commit: the personal folders should not show up.
- **Do not edit** the other person's files in the shared folders without telling them;
  use a branch and a pull request for bigger changes.

## Setting up a new PC

```
git clone https://github.com/csabamoldvai/Dubrovnik.git
cd Dubrovnik
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python dubGui\dubrovnik_workbench.py
```

Run the tests with `python -m unittest discover -s tests`. The installer is built with
`packaging\build.bat`; the packaging folder is personal, so ask for the current copy.

## Versions

The version number lives in one place, `dubLibs/version.py`. A release is a commit
that changes it, adds an entry at the top of `changelist.txt`, and is tagged
`v<version>`. Only the owner of the release makes version commits.
