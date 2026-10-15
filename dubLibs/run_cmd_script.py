"""Helpers for the "Run Script" feature of the Dubrovnik apps.

A script is a plain text file with one board command per line, exactly as it
would be typed in the Terminal:

    config
    freq 120            # text after '#' is a comment, shown while the script runs
    volt 1.9
    6; 31 2;            # ';' chains commands on one line; a last ';' is ignored
    pattern caba0000 1
    6; 2 0; wait 0
    b 0 100
"""


def split_comment(line):
    """Splits a line at the first '#': returns (command, comment). The command
    is stripped; the comment is the text after '#', stripped ('' if none)."""
    command, _, comment = line.partition('#')
    return command.strip(), comment.strip()


def parse_lines(text):
    """Returns [(line number, command, comment), ...] for every line of a script
    that has a command or a comment. A comment-only line has command ''. A ';'
    at the end of a command is removed (';' inside a line chains commands and
    is kept). Blank lines are left out. Line numbers start at 1 and refer to
    the original file."""
    lines = []
    for number, line in enumerate(text.splitlines(), 1):
        command, comment = split_comment(line)
        command = command.rstrip(';').strip()
        if command or comment:
            lines.append((number, command, comment))
    return lines


def parse(text):
    """Returns [(line number, command), ...] for the commands in a script
    (comments and blank lines left out, see parse_lines)."""
    return [(number, command) for number, command, _ in parse_lines(text) if command]


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
