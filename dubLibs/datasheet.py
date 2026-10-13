"""Help > Datasheet: finds the datasheet of the device in the socket.

A local file in the docs folder wins (it works offline and is a known version).
Otherwise the web address from the settings is opened in the default browser.
The address may contain {part}, which is replaced by the part number, e.g.

    https://www.renesas.com/en/search?keywords={part}

An address without {part} (a product-family page, say) is opened as it is.
"""
import os
import re
import urllib.parse

DEFAULT_URL = 'https://www.renesas.com/en/search?keywords={part}'
DATASHEET_EXTENSIONS = ('.pdf', '.htm', '.html')


def clean_url(text):
    """Returns text if it is a usable web address (http or https), else the
    default address"""
    text = (text or '').strip()
    parsed = urllib.parse.urlparse(text.replace('{part}', 'x'))
    if parsed.scheme in ('http', 'https') and parsed.netloc:
        return text
    return DEFAULT_URL


def part_from_status(text):
    """The part number in a status-bar text like '... Device: ATXP032'.
    Returns '' if no device is shown."""
    match = re.search(r'Device:\s*(\S+)', text or '')
    return match.group(1) if match else ''


def build_url(template, part):
    """The address to open for part"""
    template = clean_url(template)
    return template.replace('{part}', urllib.parse.quote(part, safe=''))


def _key(text):
    return re.sub(r'[^a-z0-9]', '', text.lower())


def _candidates(part):
    """Part number spellings to look for, most specific first: the full string,
    then shorter forms without the ordering suffix, e.g. AT25SL128A-MHE-T gives
    AT25SL128A-MHE, AT25SL128A, AT25SL128. Cutting is only done at a - _ or
    space, or by dropping trailing letters after the last digit, so AT25SL128
    never turns into AT25SL1."""
    found = []

    def add(text):
        key = _key(text)
        if len(key) >= 4 and key not in found:
            found.append(key)
    parts = re.split(r'([-_ ])', part)
    while parts:
        add(''.join(parts))
        parts = parts[:-2] if len(parts) > 2 else []
    for key in list(found):
        add(re.sub(r'[a-z]+$', '', key))
    return found


def find_local(folders, part):
    """Full path of a datasheet file for part in one of the folders (searched
    in order, including a 'datasheets' subfolder), or ''. The part number (or a
    shorter form of it, see _candidates) must appear in the file name, ignoring
    case, spaces, dashes and underscores. The most specific spelling wins."""
    files = []
    for folder in folders:
        for sub in ('', 'datasheets'):
            where = os.path.join(folder, sub)
            try:
                names = sorted(os.listdir(where), key=str.lower)
            except OSError:
                continue
            for name in names:
                path = os.path.join(where, name)
                if (os.path.isfile(path)
                        and name.lower().endswith(DATASHEET_EXTENSIONS)):
                    files.append((_key(os.path.splitext(name)[0]), path))
    for want in _candidates(part):
        for key, path in files:
            if want in key:
                return path
    return ''
