"""Reads firmware images: raw binary, Motorola S-record and Intel HEX.

Standard library only and no GUI code, so it can be copied into any other
program. Typical use:

    image = load_image('boot.srec')      # format detected from the content
    for address, data in image.segments: # sorted, touching blocks merged
        ...                              # program data at address
    image.size, image.start, image.end   # bytes, first address, last + 1
    image.to_bytes(fill=0xFF)            # one block, gaps filled (use with care)

A bad file raises ImageError with a readable message (line number included);
nothing is returned half-loaded. Checksums of S-record and Intel HEX lines are
always checked.

Formats
  binary    the whole file is one segment at address 0 (add your own offset)
  S-record  .srec .s19 .s28 .s37 .mot .sx   data records S1/S2/S3, count
            records S5/S6 are checked, S0 header and S7/S8/S9 are skipped
  Intel HEX .hex .ihex .ihx                 data, EOF, extended segment (02) and
            extended linear (04) address records; start records (03/05) skipped
"""
import os
import re

SREC_EXTENSIONS = ('.srec', '.s19', '.s28', '.s37', '.mot', '.sx')
IHEX_EXTENSIONS = ('.hex', '.ihex', '.ihx')
BIN_EXTENSIONS = ('.bin',)
FILE_TYPES = (                       # for a tkinter open dialog
    ('Firmware images', ' '.join('*' + e for e in
                                 BIN_EXTENSIONS + SREC_EXTENSIONS + IHEX_EXTENSIONS)),
    ('Binary files', '*.bin'),
    ('S-record files', ' '.join('*' + e for e in SREC_EXTENSIONS)),
    ('Intel HEX files', ' '.join('*' + e for e in IHEX_EXTENSIONS)),
    ('All files', '*.*'))

_SREC_LINE = re.compile(r'S[0-9]([0-9A-Fa-f]{2})+')
_IHEX_LINE = re.compile(r':([0-9A-Fa-f]{2})+')


class ImageError(ValueError):
    """The file is not a valid image (message says why and where)"""


class Image:
    """Data blocks of a firmware image: segments = [(address, bytes), ...],
    sorted by address, with touching or overlapping blocks merged."""

    def __init__(self, segments, kind='binary'):
        self.kind = kind
        self.segments = _merge(segments)

    @property
    def size(self):
        return sum(len(data) for _, data in self.segments)

    @property
    def start(self):
        return self.segments[0][0] if self.segments else 0

    @property
    def end(self):
        if not self.segments:
            return 0
        address, data = self.segments[-1]
        return address + len(data)

    def to_bytes(self, fill=0xFF):
        """One block from start to end with the gaps filled (a sparse image can
        become huge: check end - start first)"""
        out = bytearray()
        for address, data in self.segments:
            out.extend(bytes([fill]) * (address - self.start - len(out)))
            out.extend(data)
        return bytes(out)

    def describe(self):
        """One line, e.g. 'S-record: 3 segments, 12288 bytes, 0x0 to 0x2FFF'"""
        count = len(self.segments)
        return (f'{self.kind}: {count} segment{"s" if count != 1 else ""}, '
                f'{self.size} bytes, 0x{self.start:X} to 0x{self.end - 1:X}'
                if self.segments else f'{self.kind}: empty')


def _merge(segments):
    """Sorts, joins blocks that touch and checks that overlaps agree"""
    merged = []
    for address, data in sorted((s for s in segments if s[1]),
                                key=lambda s: s[0]):
        data = bytes(data)
        if merged:
            last_address, last = merged[-1]
            last_end = last_address + len(last)
            if address <= last_end:
                overlap = last_end - address
                if overlap and last[address - last_address:] != data[:overlap]:
                    raise ImageError(
                        f'conflicting data at address 0x{address:X}: two records '
                        f'overlap with different bytes')
                merged[-1] = (last_address, last + data[overlap:])
                continue
        merged.append((address, data))
    return merged


def _hex_bytes(text, where):
    try:
        return bytes.fromhex(text)
    except ValueError:
        raise ImageError(f'{where}: not hexadecimal') from None


def parse_srec(text):
    """Parses S-record text and returns an Image"""
    chunks, data_records, counts = [], 0, []
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith(';'):
            continue
        where = f'line {number}'
        if not _SREC_LINE.fullmatch(line):
            raise ImageError(f'{where}: not an S-record line')
        kind = int(line[1])
        raw = _hex_bytes(line[2:], where)
        if raw[0] != len(raw) - 1:
            raise ImageError(f'{where}: byte count does not match the line length')
        if (sum(raw) & 0xFF) != 0xFF:
            raise ImageError(f'{where}: checksum error')
        body = raw[1:-1]
        if kind in (1, 2, 3):
            width = kind + 1
            if len(body) < width:
                raise ImageError(f'{where}: record too short')
            chunks.append((int.from_bytes(body[:width], 'big'), body[width:]))
            data_records += 1
        elif kind in (5, 6):
            counts.append((number, int.from_bytes(body, 'big')))
        elif kind in (0, 7, 8, 9):
            pass                        # header / start address: nothing to load
        else:
            raise ImageError(f'{where}: unknown record type S{kind}')
    for number, count in counts:
        if count != data_records:
            raise ImageError(f'line {number}: record count says {count} data '
                             f'records but the file has {data_records}')
    if not chunks:
        raise ImageError('no data records found')
    return Image(chunks, 'S-record')


def parse_ihex(text):
    """Parses Intel HEX text and returns an Image"""
    chunks, upper, finished = [], 0, False
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        where = f'line {number}'
        if not _IHEX_LINE.fullmatch(line):
            raise ImageError(f'{where}: not an Intel HEX line')
        raw = _hex_bytes(line[1:], where)
        if len(raw) < 5 or raw[0] != len(raw) - 5:
            raise ImageError(f'{where}: byte count does not match the line length')
        if (sum(raw) & 0xFF) != 0:
            raise ImageError(f'{where}: checksum error')
        kind, offset, body = raw[3], (raw[1] << 8) | raw[2], raw[4:-1]
        if finished:
            raise ImageError(f'{where}: data after the end-of-file record')
        if kind == 0:
            chunks.append((upper + offset, body))
        elif kind == 1:
            finished = True
        elif kind == 2 and len(body) == 2:
            upper = int.from_bytes(body, 'big') << 4
        elif kind == 4 and len(body) == 2:
            upper = int.from_bytes(body, 'big') << 16
        elif kind in (3, 5):
            pass                        # start address: nothing to load
        else:
            raise ImageError(f'{where}: unknown or malformed record type {kind:02X}')
    if not chunks:
        raise ImageError('no data records found')
    return Image(chunks, 'Intel HEX')


def detect_format(data, filename=''):
    """'binary', 'srec' or 'ihex' for the file content. A .bin file is always
    binary; otherwise the first line decides, and a text format that was
    recognised by its extension only is reported so the parser can explain what
    is wrong."""
    extension = os.path.splitext(filename)[1].lower()
    if extension in BIN_EXTENSIONS:
        return 'binary'
    head = data[:512]
    if head.startswith(b'\xef\xbb\xbf'):
        head = head[3:]
    first = next((ln.strip() for ln in
                  head.decode('ascii', errors='replace').splitlines()
                  if ln.strip()), '')
    if _SREC_LINE.fullmatch(first):
        return 'srec'
    if _IHEX_LINE.fullmatch(first):
        return 'ihex'
    if extension in SREC_EXTENSIONS:
        return 'srec'
    if extension in IHEX_EXTENSIONS:
        return 'ihex'
    return 'binary'


def parse_image(data, filename=''):
    """Image from the bytes of a file (format detected, see detect_format)"""
    kind = detect_format(data, filename)
    if kind == 'binary':
        if not data:
            raise ImageError('the file is empty')
        return Image([(0, data)], 'binary')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ImageError('the file is not a text file') from None
    return parse_srec(text) if kind == 'srec' else parse_ihex(text)


def load_image(path):
    """Reads the file at path (OSError if it can't be read) and returns an Image"""
    with open(path, 'rb') as fh:
        data = fh.read()
    return parse_image(data, path)
