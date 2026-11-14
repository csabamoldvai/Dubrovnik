"""Programming the SD card of the Dubrovnik board with NXP's MfgTool2 (no GUI code).

The Workbench does not run the programming: MfgTool2.exe has no command line and its result (the
green bar) cannot be read. The Workbench guides the user (see dubGui/dialogs/sd_wizard.py) and
does what can be done safely here:

    problem = tool_problem(folder)           # None, or why the tool folder is not usable
    releases = find_releases(folder)         # the releases in a folder, newest first
    release = open_release(path)             # a .zip from Teams, a folder, or a boot_image.sb
    release.date, release.notes()            # datetime.date (or None), text of relnotes.docx (or None)
    target, backup = release.install(folder) # boot_image.sb into the tool's profile folder
    built = banner_time(terminal_text)       # datetime of "Flash Memory Test Bench - Dec  5 2024 ..."
    verdict = compare(release.date, built)   # 'match', 'differ' or 'unknown'

A release is named yyyymmdd (for example 20260916) and has boot_image.sb and relnotes.docx. Downloaded
from Teams it is a zip (20260916.zip holding 20260916/boot_image.sb and 20260916/relnotes.docx); it
is read from the zip, nothing is unpacked to disk except the one file copied into the tool. The board
prints the date and time the software was built when it starts, in the compiler's format.
"""
import datetime
import io
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
MAX_DOCX_BYTES = 20_000_000             # a release note file itself
MAX_IMAGE_BYTES = 256 * 1024 * 1024     # a boot image is about 100 KB: anything this big is wrong

MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
BANNER = re.compile(r'Flash Memory Test Bench\s*-\s*([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{4})\s+'
                    r'(\d{1,2}):(\d{2}):(\d{2})')


class ReleaseError(Exception):
    """A release that cannot be used; the message says why"""


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


def date_from_name(name):
    """The date in a name made of 8 digits (yyyymmdd), else None"""
    if not re.fullmatch(r'\d{8}', name):
        return None
    try:
        return datetime.date(int(name[:4]), int(name[4:6]), int(name[6:]))
    except ValueError:
        return None


def release_date(sb_path):
    """The date of the release a boot_image.sb belongs to: its folder is named yyyymmdd. None if
    the folder has another name (or is not a real date)."""
    return date_from_name(os.path.basename(os.path.dirname(os.path.abspath(sb_path))))


def docx_text(data, limit=3000):
    """The text of a .docx given as bytes (paragraphs, one per line, cut at limit characters), or
    None if it cannot be read. A .docx is a zip with word/document.xml."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as docx:
            if docx.getinfo('word/document.xml').file_size > MAX_DOCUMENT_BYTES:
                return None                     # not a release note: do not unpack a huge part
            xml = docx.read('word/document.xml')
        # The file comes from outside: Word never writes a DOCTYPE or entities, but a crafted file
        # could use them to blow up the XML parser (billion laughs), so such a file is refused.
        if b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():
            return None
        root = ET.fromstring(xml)
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


def read_relnotes(folder, limit=3000):
    """The text of relnotes.docx in folder, or None if there is no such file or it cannot be read"""
    path = os.path.join(folder, RELNOTES_NAME)
    try:
        if os.path.getsize(path) > MAX_DOCX_BYTES:
            return None
        with open(path, 'rb') as fh:
            data = fh.read()
    except OSError:
        return None
    return docx_text(data, limit)


def same_content(path_a, path_b):
    """True if the two files have the same bytes. Read every time: filecmp.cmp remembers its
    answers by file size and modification time, and on Windows two different files written within
    a few milliseconds can look the same to it, which would keep the wrong image in the tool."""
    if os.path.getsize(path_a) != os.path.getsize(path_b):
        return False
    with open(path_a, 'rb') as a, open(path_b, 'rb') as b:
        while True:
            chunk = a.read(1024 * 1024)
            if chunk != b.read(len(chunk)):
                return False
            if not chunk:
                return True


def install_stream(open_source, tool_folder, expected_size=None):
    """Writes the image that open_source() gives (a binary file object) as boot_image.sb into the
    profile folder of the tool. It is written under a temporary name first and then moved into
    place, so the tool never sees half a file. A boot_image.sb that is already there and differs is
    kept as boot_image.sb.bak (an identical one is left alone). Returns (target path, backup path or
    None); raises OSError or ReleaseError if anything fails."""
    folder = profile_folder(tool_folder)
    target = os.path.join(folder, IMAGE_NAME)
    temp = target + '.tmp'
    try:
        written = 0
        with open_source() as source, open(temp, 'wb') as out:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_IMAGE_BYTES:
                    raise ReleaseError('The boot image is much bigger than expected: not used.')
                out.write(chunk)
        if expected_size is not None and written != expected_size:
            raise OSError(f'Only {written} of {expected_size} bytes were copied')
        backup = None
        if os.path.isfile(target):
            if same_content(temp, target):
                return target, None             # the same image is there already
            backup = os.path.join(folder, BACKUP_NAME)
            shutil.copyfile(target, backup)
        os.replace(temp, target)
        return target, backup
    except zipfile.BadZipFile as e:
        raise ReleaseError(f'The zip file is damaged: {e}') from e
    finally:
        if os.path.exists(temp):
            os.remove(temp)


def install_image(sb_path, tool_folder):
    """Copies the file sb_path as boot_image.sb into the profile folder of the tool (see
    install_stream). Returns (target path, backup path or None)."""
    return install_stream(lambda: open(sb_path, 'rb'), tool_folder)


class Release:
    """One release of the board software: a .zip from Teams, a folder, or a boot_image.sb file.
    path: what the user chose. kind: 'zip', 'folder' or 'file'. date: datetime.date or None (from
    the name 20260916). label: a short text for a list. Made by open_release()."""

    def __init__(self, path, kind, date, member=None, notes_member=None):
        self.path, self.kind, self.date = path, kind, date
        self.member, self.notes_member = member, notes_member   # names inside a zip
        name = os.path.basename(path)
        self.label = {'zip': name, 'folder': f'{name}  (folder)', 'file': name}[kind]

    def notes(self, limit=3000):
        """The text of relnotes.docx of this release, or None if there is none"""
        try:
            if self.kind == 'zip':
                if not self.notes_member:
                    return None
                with zipfile.ZipFile(self.path) as archive:
                    if archive.getinfo(self.notes_member).file_size > MAX_DOCX_BYTES:
                        return None
                    return docx_text(archive.read(self.notes_member), limit)
            folder = self.path if self.kind == 'folder' else os.path.dirname(self.path)
            return read_relnotes(folder_with_image(folder) or folder, limit)
        except (OSError, KeyError, zipfile.BadZipFile):
            return None

    def install(self, tool_folder):
        """Puts the image of this release into the tool as boot_image.sb. Returns (target, backup
        or None); raises OSError or ReleaseError."""
        if self.kind == 'zip':
            archive = zipfile.ZipFile(self.path)
            size = archive.getinfo(self.member).file_size
            try:
                return install_stream(lambda: archive.open(self.member), tool_folder, size)
            finally:
                archive.close()
        if self.kind == 'folder':
            sb = os.path.join(folder_with_image(self.path) or self.path, IMAGE_NAME)
        else:
            sb = self.path
        return install_image(sb, tool_folder)


def folder_with_image(folder):
    """folder itself, or its only subfolder (Teams puts 20260916 inside 20260916), whichever has
    boot_image.sb; None if neither has"""
    if os.path.isfile(os.path.join(folder, IMAGE_NAME)):
        return folder
    try:
        inner = [os.path.join(folder, n) for n in os.listdir(folder)
                 if os.path.isdir(os.path.join(folder, n))]
    except OSError:
        return None
    if len(inner) == 1 and os.path.isfile(os.path.join(inner[0], IMAGE_NAME)):
        return inner[0]
    return None


def zip_members(archive):
    """(boot image member, release notes member or None) of a zip: the boot_image.sb nearest to the
    top, and the relnotes.docx in the same folder. Raises ReleaseError if there is no boot image."""
    names = [i.filename for i in archive.infolist() if not i.is_dir()]
    images = sorted((n for n in names if n.replace('\\', '/').split('/')[-1].lower() == IMAGE_NAME),
                    key=lambda n: n.count('/'))
    if not images:
        raise ReleaseError(f'There is no {IMAGE_NAME} in the zip file.')
    image = images[0]
    prefix = image[:len(image) - len(IMAGE_NAME)]
    notes = next((n for n in names if n.lower() == (prefix + RELNOTES_NAME).lower()), None)
    return image, notes


def open_release(path):
    """A Release from a .zip, a folder or a boot_image.sb file. Raises ReleaseError (the message
    says what is wrong) if it has no boot image or cannot be read."""
    path = os.path.normpath(path)
    try:
        if os.path.isdir(path):
            inner = folder_with_image(path)
            if inner is None:
                raise ReleaseError(f'There is no {IMAGE_NAME} in the folder.')
            return Release(path, 'folder', date_from_name(os.path.basename(path))
                           or date_from_name(os.path.basename(inner)))
        if path.lower().endswith('.zip'):
            with zipfile.ZipFile(path) as archive:
                member, notes = zip_members(archive)
            parts = member.replace('\\', '/').split('/')
            date = (date_from_name(parts[-2]) if len(parts) > 1 else None) \
                or date_from_name(os.path.splitext(os.path.basename(path))[0])
            return Release(path, 'zip', date, member, notes)
        if os.path.isfile(path):
            return Release(path, 'file', release_date(path))
    except zipfile.BadZipFile as e:
        raise ReleaseError(f'The zip file is damaged: {e}') from e
    except OSError as e:
        raise ReleaseError(f'It could not be read: {e}') from e
    raise ReleaseError('The file or folder was not found.')


def find_releases(folder):
    """The releases in folder (zip files and folders with a boot_image.sb), newest first: sorted by
    date, a release without a date last. Anything else in the folder is ignored."""
    found = []
    try:
        names = os.listdir(folder)
    except OSError:
        return found
    for name in names:
        path = os.path.join(folder, name)
        if not (os.path.isdir(path) or name.lower().endswith('.zip')):
            continue
        try:
            found.append(open_release(path))
        except ReleaseError:
            continue
    found.sort(key=lambda r: (r.date is not None, r.date or datetime.date.min, r.kind == 'zip'),
               reverse=True)
    return found


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
    is missing (no date in the name, or no banner seen). The time of day is not compared: the
    name has none."""
    if release is None or built is None:
        return 'unknown'
    return 'match' if built.date() == release else 'differ'
