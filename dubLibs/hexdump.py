"""Hex dump formatting, like a hex editor: address, hex bytes, ASCII.

Standard library only and no GUI code, so it can be reused in other programs.

    text = format_hexdump(data, address=0x2000)
    00002000  00 00 02 20 19 70 10 03  37 71 00 00 73 79 00 00  |... .p..7q..sy..|
    00002010  CB 79 00 00 97 A0 00 00                            |.y......|

A first address that does not start a row is padded, so the addresses on the
left always are multiples of the row size (like a hex editor).

format_segments() lays out a whole image (several blocks with gaps) for a viewer
and returns an index that line_for_address() uses to jump to an address.

bytes_from_reply() turns the board's reply in binary display mode ("00 ff ...",
32 values per line) back into bytes, so the PC can lay the data out itself.
"""
import bisect
import re

ROW_SIZES = (8, 16, 32)
DEFAULT_ROW = 16
GROUP = 8                          # an extra space after this many bytes

_HEX_LINE = re.compile(r'(?:[0-9a-fA-F]{2}(?:\s+|$))+')


def printable(value):
    """The character shown in the ASCII column"""
    return chr(value) if 0x20 <= value < 0x7F else '.'


def format_hexdump(data, address=0, per_row=DEFAULT_ROW, show_ascii=True,
                   upper=True, gap=True):
    """Returns the dump of data (bytes) that starts at address, one text line
    per row, without a trailing newline.
    per_row: bytes per row (8, 16 or 32); show_ascii: add the ASCII column;
    upper: upper case hex digits; gap: extra space after every 8 bytes."""
    if per_row not in ROW_SIZES:
        raise ValueError(f'bytes per row must be one of {ROW_SIZES}')
    digits = 'X' if upper else 'x'
    lines = []
    first = address - address % per_row          # row that holds the first byte
    last = address + len(data)
    row_address = first
    while row_address < last:
        cells, chars = [], []
        for column in range(per_row):
            where = row_address + column
            if address <= where < last:
                value = data[where - address]
                cells.append(format(value, '02' + digits))
                chars.append(printable(value))
            else:
                cells.append('  ')                # padding before / after data
                chars.append(' ' if where < address else '')
            if gap and column % GROUP == GROUP - 1 and column != per_row - 1:
                cells.append('')                  # joins to one extra space
        line = format(row_address, '08' + digits) + '  ' + ' '.join(cells)
        if show_ascii:
            line += '  |' + ''.join(chars) + '|'
        lines.append(line.rstrip() if not show_ascii else line)
        row_address += per_row
    return '\n'.join(lines)


def bytes_from_reply(reply, command_line=''):
    """The data bytes in the board's reply to a read in binary display mode.
    command_line (the command that was sent) is dropped first: it can look
    like a row of bytes. Lines that are not rows of two-digit hex values
    (the prompt, messages) are ignored. Returns bytes."""
    out = bytearray()
    command = command_line.strip()
    skipped = not command
    for line in reply.replace('\r', '').split('\n'):
        stripped = line.strip()
        if not skipped and stripped.endswith(command):
            skipped = True                        # the echoed command
            continue
        if stripped and _HEX_LINE.fullmatch(stripped):
            out.extend(bytes.fromhex(stripped.replace(' ', '').replace('\t', '')))
    return bytes(out)


def format_segments(segments, offset=0, limit=None, full_if_at_most=0,
                    max_segments=None, **options):
    """Dump of an image, a heading line per segment (with the size of the gap
    before it). segments: [(address, bytes), ...] sorted; offset is added to
    every address (where the data will be written). options go to
    format_hexdump (per_row, show_ascii, upper, gap).
    limit: show only the first `limit` bytes of each segment, except segments
    of at most `full_if_at_most` bytes; max_segments: show only the first few
    segments. Returns (text, rows): rows is a list of (row_address, line_number)
    for the data rows (line numbers start at 1), for line_for_address()."""
    lines, rows = [], []
    previous_end = None
    shown = segments if max_segments is None else segments[:max_segments]
    for number, (address, data) in enumerate(shown, 1):
        start = address + offset
        head = (f'--- segment {number} of {len(segments)}: 0x{start:X} to '
                f'0x{start + len(data) - 1:X} ({len(data)} bytes)')
        if previous_end is not None and start > previous_end:
            head += f', gap of {start - previous_end} bytes before'
        lines.append(head + ' ---')
        count = len(data)
        if limit is not None and count > full_if_at_most:
            count = min(count, limit)
        per_row = options.get('per_row', DEFAULT_ROW)
        row_address = start - start % per_row
        for row in format_hexdump(data[:count], start, **options).split(chr(10)):
            lines.append(row)
            rows.append((row_address, len(lines)))
            row_address += per_row
        if count < len(data):
            lines.append(f'... {len(data) - count} more bytes')
        previous_end = start + len(data)
    if len(shown) < len(segments):
        lines.append(f'... and {len(segments) - len(shown)} more segments')
    return chr(10).join(lines), rows


def line_for_address(rows, address):
    """Line number of the row that holds address, or of the next row after it
    when address lies in a gap; the last row if it is beyond the end. None
    when there are no rows."""
    if not rows:
        return None
    per_row_starts = [r[0] for r in rows]
    index = bisect.bisect_right(per_row_starts, address) - 1
    if index >= 0 and address - rows[index][0] < _row_span(rows, index):
        return rows[index][1]
    index = bisect.bisect_left(per_row_starts, address)
    return rows[min(index, len(rows) - 1)][1]


def _row_span(rows, index):
    """Bytes covered by a row: the distance to the next row of the same
    segment (consecutive line numbers), else the distance used by its
    predecessor, else 8"""
    if index + 1 < len(rows) and rows[index + 1][1] == rows[index][1] + 1:
        return rows[index + 1][0] - rows[index][0]
    if index > 0 and rows[index][1] == rows[index - 1][1] + 1:
        return rows[index][0] - rows[index - 1][0]
    return 8
