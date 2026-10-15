"""The Tools menu is built from the scripts in the 'tools' folder.

A Python script (.py) appears in the menu if one of its first 20 lines is

    # TOOL: Name shown in the menu

A command script (.txt or .scr, the kind File > Scripts > Run Command Script runs)
appears if its FIRST line is the same header. ``# TOOLS:`` is accepted too.

Optional header lines of a Python script (anywhere in the first 20 lines):

    # DESCRIPTION: one line shown in the status bar after the tool is started
    # CONFIRM: question the user must answer Yes to before the tool starts

The Python scripts are ordinary Python scripts that use the ``dub`` object (see
dubLibs/run_py_script.py). Dropping a new file into the folder is all it takes to
add a tool; the menu is rebuilt every time it is opened.
"""
import os

HEADER_LINES = 20
COMMAND_EXTENSIONS = ('.txt', '.scr')
NAME_KEYS = ('TOOLS', 'TOOL')


def _name_of(line):
    """The menu name in a '# TOOL: name' (or '# TOOLS:') line, '' if it is another line"""
    line = line.strip()
    for key in NAME_KEYS:
        prefix = f'# {key}:'
        if line.upper().startswith(prefix):
            return line[len(prefix):].strip()
    return ''


def find_tools(folder):
    """Returns [{'name', 'path', 'kind', 'description', 'confirm'}, ...] for the
    scripts in folder that have a tool header. kind is 'python' or 'command'.
    The Python tools come first, then the command scripts, each sorted by name."""
    found = {'python': [], 'command': []}
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    for filename in names:
        ext = os.path.splitext(filename)[1].lower()
        kind = 'python' if ext == '.py' else 'command' if ext in COMMAND_EXTENSIONS else None
        if kind is None:
            continue
        path = os.path.join(folder, filename)
        info = {'name': '', 'path': path, 'kind': kind, 'description': '', 'confirm': ''}
        try:
            with open(path, encoding='utf-8-sig') as fh:
                for _, line in zip(range(HEADER_LINES if kind == 'python' else 1), fh):
                    info['name'] = _name_of(line) or info['name']
                    if kind == 'python':
                        for key in ('DESCRIPTION', 'CONFIRM'):
                            prefix = f'# {key}:'
                            if line.strip().upper().startswith(prefix):
                                info[key.lower()] = line.strip()[len(prefix):].strip()
        except (OSError, UnicodeDecodeError):
            continue
        # a backslash followed by n in the header text means a new line
        info['confirm'] = info['confirm'].replace('\\n', '\n')
        if info['name']:
            found[kind].append(info)
    return [t for kind in ('python', 'command')
            for t in sorted(found[kind], key=lambda t: t['name'].lower())]
