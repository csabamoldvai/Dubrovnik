"""Programming the SD card of the Dubrovnik board with NXP's MfgTool2 (no GUI code).

The Workbench does not run the programming: MfgTool2.exe has no command line and its result (the
green bar) cannot be read. The Workbench guides the user (see dubGui/dialogs/sd_wizard.py) and
does what can be done safely here:

    problem = tool_problem(folder)                 # None, or why the tool folder is not usable
    date = release_date(sb_path)                   # datetime.date from the folder name 20260916
    text = read_relnotes(os.path.dirname(sb_path)) # the text of relnotes.docx, or None
    target, backup = install_image(sb_path, folder)  # copy as boot_image.sb into the tool's profile
    built = banner_time(terminal_text)             # datetime of "Flash Memory Test Bench - Dec  5 2024 ..."
    verdict = compare(date, built)                 # 'match', 'differ' or 'unknown'

A release is a folder named yyyymmdd (for example 20260916) with boot_image.sb and relnotes.docx. The
board prints the date and time the software was built when it starts, in the compiler's format.
"""
import datetime
import filecmp
import os
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET

TOOL_NAME = 'MfgTool2.exe'
IMAGE_NAME = 'boot_image.sb'            # the profile of the tool looks for exactly this name
BACKUP_NAME = 'boot_image.sb.bak'
PROFILE_FOLDER = os.path.join('Profiles', 'MXRT105X', 'OS Firmware')
RELNOTES_NAME = 'relnotes.docx'
MAX_DOCUMENT_BYTES = 5_000_000          # the text part of a release note is a few KB

MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
BANNER = re.compile(r'Flash Memory Test Bench\s*-\s*([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{4})\s+'
                    r'(\d{1,2}):(\d{2}):(\d{2})')


def profile_folder(tool_folder):
    """The folder of the tool where boot_image.sb has to be"""
    return os.path.join(tool_folder, PROFILE_FOLDER)


def tool_problem(tool_folder):
    """None if tool_folder is a usable MfgTools folder, else a sentence saying what is wrong"""
    if not tool_folder:
        return 'The folder with MfgTool2.exe is not set (Preferences > Configure Paths > SD card tool).'
    if not os.path.isdir(tool_folder):
        return f'The SD card tool folder was not found:\n{tool_folder}'
    if not os.path.isfile(os.path.join(tool_folder, TOOL_NAME)):
        return f'{TOOL_NAME} is not in the folder:\n{tool_folder}'
    if not os.path.isdir(profile_folder(tool_folder)):
        return f'The folder has no "{PROFILE_FOLDER}" inside, so it is not the MfgTools folder:\n{tool_folder}'
    return None


def release_date(sb_path):
    """The date of the release a boot_image.sb belongs to: its folder is named yyyymmdd. None if
    the folder has another name (or is not a real date)."""
    name = os.path.basename(os.path.dirname(os.path.abspath(sb_path)))
    if not re.fullmatch(r'\d{8}', name):
        return None
    try:
        return datetime.date(int(name[:4]), int(name[4:6]), int(name[6:]))
    except ValueError:
        return None


def read_relnotes(folder, limit=3000):
    """The text of relnotes.docx in folder (paragraphs, one per line, cut at limit characters), or
    None if there is no such file or it cannot be read. A .docx is a zip with word/document.xml."""
    path = os.path.join(folder, RELNOTES_NAME)
    try:
        with zipfile.ZipFile(path) as docx:
            if docx.getinfo('word/document.xml').file_size > MAX_DOCUMENT_BYTES:
                return None                     # not a release note: do not unpack a huge part
            data = docx.read('word/document.xml')
        # The file comes from outside: Word never writes a DOCTYPE or entities, but a crafted file
        # could use them to blow up the XML parser (billion laughs), so such a file is refused.
        if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
            return None
        root = ET.fromstring(data)
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError):
        return None
    word = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    lines = []
    for paragraph in root.iter(word + 'p'):
        text = ''.join(node.text or '' for node in paragraph.iter(word + 't')).strip()
        if text:
            lines.append(text)
    text = '\n'.join(lines)
    return text if len(text) <= limit else text[:limit].rstrip() + ' ...'


def install_image(sb_path, tool_folder):
    """Copies sb_path as boot_image.sb into the profile folder of the tool. A boot_image.sb that is
    already there is kept as boot_image.sb.bak (the one before it is replaced). The copy is compared
    with the source. Returns (target path, backup path or None); raises OSError if anything fails."""
    folder = profile_folder(tool_folder)
    target = os.path.join(folder, IMAGE_NAME)
    backup = None
    if os.path.isfile(target) and not filecmp.cmp(sb_path, target, shallow=False):
        backup = os.path.join(folder, BACKUP_NAME)
        shutil.copyfile(target, backup)
    shutil.copyfile(sb_path, target)
    if not filecmp.cmp(sb_path, target, shallow=False):
        raise OSError(f'The copy in {folder} is not the same as the original')
    return target, backup


def banner_time(text):
    """The build date and time from the start-up banner of the board
    ('Flash Memory Test Bench - Dec  5 2024 17:51:33') as a datetime; None if the text has none.
    With several banners the last one counts."""
    found = None
    for match in BANNER.finditer(text):
        month, day, year, hour, minute, second = match.groups()
        if month not in MONTHS:
            continue
        try:
            found = datetime.datetime(int(year), MONTHS.index(month) + 1, int(day),
                                      int(hour), int(minute), int(second))
        except ValueError:
            continue
    return found


def compare(release, built):
    """'match' if the board's build date is the release date, 'differ' if not, 'unknown' if either
    is missing (no date in the folder name, or no banner seen). The time of day is not compared:
    the folder name has none."""
    if release is None or built is None:
        return 'unknown'
    return 'match' if built.date() == release else 'differ'
