"""Helpers for the "Run Script" feature of the Dubrovnik apps.

A script is a plain text file with one board command per line, exactly as it
would be typed in the Terminal:

    config
    freq 120            # text after '#' is a comment
    volt 1.9
    6; 31 2;            # ';' chains commands on one line; a last ';' is ignored
    pattern caba0000 1
    6; 2 0; wait 0
    b 0 100
"""


def parse(text):
    """Returns [(line number, command), ...] for the commands in a script.
    Comments ('#' to the end of the line), blank lines and a ';' at the end of
    a line are removed (';' inside a line chains commands and is kept).
    Line numbers start at 1 and refer to the original file."""
    commands = []
    for number, line in enumerate(text.splitlines(), 1):
        line = line.split('#', 1)[0].strip().rstrip(';').strip()
        if line:
            commands.append((number, line))
    return commands


def is_error(reply):
    """True if the board's reply is an error message ('Error: ...')"""
    return reply.strip().lower().startswith('error')


def clean_pasted(text):
    """Turns pasted text into one Terminal command line.

    Text copied from slides or documents often carries a leading '>>>' prompt,
    line breaks and invisible characters. Each line loses its '>>>' prompt and
    its unprintable characters, empty lines are dropped, and the remaining lines
    are chained with '; ' (the board runs 'a; b' as two commands)."""
    import re
    parts = []
    for line in text.splitlines():
        line = line.replace(' ', ' ')
        line = ''.join(ch for ch in line if ch.isprintable())
        line = re.sub(r'^(\s*>>>\s*)+', '', line).strip()
        if line:
            parts.append(line.rstrip(';').strip())
    return '; '.join(p for p in parts if p)
