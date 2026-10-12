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


def find_local(folders, part):
    """Full path of a datasheet file for part in one of the folders (searched
    in order, including a 'datasheets' subfolder), or ''. The part number must
    appear in the file name, ignoring case, spaces, dashes and underscores."""
    want = _key(part)
    if not want:
        return ''
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
                        and name.lower().endswith(DATASHEET_EXTENSIONS)
                        and want in _key(os.path.splitext(name)[0])):
                    return path
    return ''
