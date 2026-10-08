"""The Tools menu is built from the Python scripts in the 'tools' folder.

A script appears in the menu if one of its first lines is

    # TOOL: Name shown in the menu

Optional header lines (anywhere in the first 20 lines):

    # DESCRIPTION: one line shown in the status bar after the tool is started
    # CONFIRM: question the user must answer Yes to before the tool starts

The scripts are ordinary Python scripts that use the ``dub`` object (see
dubLibs/run_py_script.py). Dropping a new file into the folder is all it takes to
add a tool; the menu is rebuilt every time it is opened.
"""
import os

HEADER_LINES = 20


def find_tools(folder):
    """Returns [{'name', 'path', 'description', 'confirm'}, ...] sorted by name
    for the scripts in folder that have a '# TOOL:' header."""
    tools = []
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return tools
    for filename in names:
        if not filename.lower().endswith('.py'):
            continue
        path = os.path.join(folder, filename)
        info = {'name': '', 'path': path, 'description': '', 'confirm': ''}
        try:
            with open(path, encoding='utf-8-sig') as fh:
                for _, line in zip(range(HEADER_LINES), fh):
                    line = line.strip()
                    for key in ('TOOL', 'DESCRIPTION', 'CONFIRM'):
                        prefix = f'# {key}:'
                        if line.upper().startswith(prefix):
                            field = 'name' if key == 'TOOL' else key.lower()
                            info[field] = line[len(prefix):].strip()
        except (OSError, UnicodeDecodeError):
            continue
        # a backslash followed by n in the header text means a new line
        info['confirm'] = info['confirm'].replace('\\n', '\n')
        if info['name']:
            tools.append(info)
    return sorted(tools, key=lambda t: t['name'].lower())
