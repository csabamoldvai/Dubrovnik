"""Tests for dubLibs/sd_card.py: tool folder check, release date, release notes, installing the
image, the board's banner date.
Run:  python -m unittest discover -s tests"""
import datetime
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dubLibs import sd_card

BANNER = """>>>

************************************************
 Flash Memory Test Bench - Dec  5 2024 17:51:33
************************************************

Detecting memory part...
"""


def make_tool(root):
    folder = os.path.join(root, 'mfgtools-rel')
    os.makedirs(sd_card.profile_folder(folder))
    with open(os.path.join(folder, sd_card.TOOL_NAME), 'wb') as fh:
        fh.write(b'MZ')
    return folder


def make_release(root, name='20260916', data=b'image-1', notes=None):
    folder = os.path.join(root, name)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, sd_card.IMAGE_NAME)
    with open(path, 'wb') as fh:
        fh.write(data)
    if notes is not None:
        document = ('<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
                    'wordprocessingml/2006/main"><w:body>' + ''.join(
                        f'<w:p><w:r><w:t>{line}</w:t></w:r></w:p>' for line in notes)
                    + '</w:body></w:document>')
        with zipfile.ZipFile(os.path.join(folder, sd_card.RELNOTES_NAME), 'w') as docx:
            docx.writestr('word/document.xml', document)
    return path


class SdCardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name

    def test_tool_problem_says_what_is_wrong(self):
        self.assertIn('not set', sd_card.tool_problem(''))
        self.assertIn('not found', sd_card.tool_problem(os.path.join(self.root, 'nope')))
        self.assertIn('MfgTool2.exe is not in', sd_card.tool_problem(self.root))
        folder = make_tool(self.root)
        self.assertIsNone(sd_card.tool_problem(folder))
        os.rmdir(sd_card.profile_folder(folder))
        self.assertIn('OS Firmware', sd_card.tool_problem(folder))

    def test_release_date_comes_from_the_folder_name(self):
        path = make_release(self.root, '20260916')
        self.assertEqual(sd_card.release_date(path), datetime.date(2026, 9, 16))
        self.assertIsNone(sd_card.release_date(make_release(self.root, 'latest')))
        self.assertIsNone(sd_card.release_date(make_release(self.root, '20261345')))
        self.assertIsNone(sd_card.release_date(make_release(self.root, '2026091')))

    def test_release_notes_text(self):
        path = make_release(self.root, notes=['Adding support for AT25SF0321C', '', 'Fixed X'])
        self.assertEqual(sd_card.read_relnotes(os.path.dirname(path)),
                         'Adding support for AT25SF0321C\nFixed X')

    def test_release_notes_missing_or_damaged_is_none(self):
        path = make_release(self.root)
        self.assertIsNone(sd_card.read_relnotes(os.path.dirname(path)))
        with open(os.path.join(os.path.dirname(path), sd_card.RELNOTES_NAME), 'w') as fh:
            fh.write('not a zip')
        self.assertIsNone(sd_card.read_relnotes(os.path.dirname(path)))

    def test_release_notes_with_entities_are_refused(self):
        path = make_release(self.root)
        evil = ('<?xml version="1.0"?><!DOCTYPE d [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body><w:p><w:r><w:t>&b;</w:t></w:r></w:p></w:body></w:document>')
        with zipfile.ZipFile(os.path.join(os.path.dirname(path), sd_card.RELNOTES_NAME), 'w') as docx:
            docx.writestr('word/document.xml', evil)
        self.assertIsNone(sd_card.read_relnotes(os.path.dirname(path)))

    def test_huge_release_notes_part_is_refused(self):
        path = make_release(self.root)
        with zipfile.ZipFile(os.path.join(os.path.dirname(path), sd_card.RELNOTES_NAME), 'w',
                             zipfile.ZIP_DEFLATED) as docx:
            docx.writestr('word/document.xml', b'<a>' + b'x' * (sd_card.MAX_DOCUMENT_BYTES + 1) + b'</a>')
        self.assertIsNone(sd_card.read_relnotes(os.path.dirname(path)))

    def test_long_release_notes_are_cut(self):
        path = make_release(self.root, notes=['x' * 5000])
        text = sd_card.read_relnotes(os.path.dirname(path), limit=100)
        self.assertEqual(len(text), 104)
        self.assertTrue(text.endswith(' ...'))

    def test_install_copies_as_boot_image_sb(self):
        tool = make_tool(self.root)
        sb = make_release(self.root, data=b'new image')
        target, backup = sd_card.install_image(sb, tool)
        self.assertEqual(target, os.path.join(sd_card.profile_folder(tool), 'boot_image.sb'))
        self.assertIsNone(backup)
        with open(target, 'rb') as fh:
            self.assertEqual(fh.read(), b'new image')

    def test_install_keeps_the_previous_image_as_a_backup(self):
        tool = make_tool(self.root)
        old = make_release(self.root, '20250101', data=b'old image')
        new = make_release(self.root, '20260916', data=b'new image')
        sd_card.install_image(old, tool)
        target, backup = sd_card.install_image(new, tool)
        with open(backup, 'rb') as fh:
            self.assertEqual(fh.read(), b'old image')
        with open(target, 'rb') as fh:
            self.assertEqual(fh.read(), b'new image')

    def test_installing_the_same_image_again_keeps_the_backup(self):
        tool = make_tool(self.root)
        old = make_release(self.root, '20250101', data=b'old image')
        new = make_release(self.root, '20260916', data=b'new image')
        sd_card.install_image(old, tool)
        sd_card.install_image(new, tool)
        _target, backup = sd_card.install_image(new, tool)      # same again: nothing to back up
        self.assertIsNone(backup)
        with open(os.path.join(sd_card.profile_folder(tool), sd_card.BACKUP_NAME), 'rb') as fh:
            self.assertEqual(fh.read(), b'old image')

    def test_banner_time(self):
        self.assertEqual(sd_card.banner_time(BANNER), datetime.datetime(2024, 12, 5, 17, 51, 33))
        self.assertIsNone(sd_card.banner_time('no banner here'))
        self.assertIsNone(sd_card.banner_time('Flash Memory Test Bench - Xyz  5 2024 17:51:33'))

    def test_the_last_banner_counts(self):
        text = BANNER + BANNER.replace('Dec  5 2024', 'Sep 16 2026')
        self.assertEqual(sd_card.banner_time(text).date(), datetime.date(2026, 9, 16))

    def test_compare(self):
        built = datetime.datetime(2026, 9, 16, 8, 0, 0)
        self.assertEqual(sd_card.compare(datetime.date(2026, 9, 16), built), 'match')
        self.assertEqual(sd_card.compare(datetime.date(2026, 9, 15), built), 'differ')
        self.assertEqual(sd_card.compare(None, built), 'unknown')
        self.assertEqual(sd_card.compare(datetime.date(2026, 9, 16), None), 'unknown')


def notes_docx(lines):
    """The bytes of a minimal relnotes.docx"""
    import io
    document = ('<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
                'wordprocessingml/2006/main"><w:body>' + ''.join(
                    f'<w:p><w:r><w:t>{line}</w:t></w:r></w:p>' for line in lines)
                + '</w:body></w:document>')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as docx:
        docx.writestr('word/document.xml', document)
    return buffer.getvalue()


def make_zip(root, name='20260916.zip', inner='20260916/', image=b'zip image', notes=('Note one',)):
    """A zip like the one Teams makes: <inner>boot_image.sb and <inner>relnotes.docx"""
    path = os.path.join(root, name)
    with zipfile.ZipFile(path, 'w') as archive:
        if image is not None:
            archive.writestr(inner + 'boot_image.sb', image)
        if notes is not None:
            archive.writestr(inner + 'relnotes.docx', notes_docx(notes))
    return path


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name

    def test_a_teams_zip_is_a_release(self):
        release = sd_card.open_release(make_zip(self.root))
        self.assertEqual((release.kind, release.date), ('zip', datetime.date(2026, 9, 16)))
        self.assertEqual(release.notes(), 'Note one')

    def test_a_zip_without_a_folder_inside_takes_the_date_from_its_name(self):
        release = sd_card.open_release(make_zip(self.root, '20260918.zip', inner=''))
        self.assertEqual(release.date, datetime.date(2026, 9, 18))
        self.assertEqual(release.notes(), 'Note one')

    def test_a_zip_with_another_name_and_no_date_folder_has_no_date(self):
        release = sd_card.open_release(make_zip(self.root, 'latest.zip', inner='fw/'))
        self.assertIsNone(release.date)

    def test_a_zip_without_release_notes(self):
        release = sd_card.open_release(make_zip(self.root, notes=None))
        self.assertIsNone(release.notes())

    def test_a_zip_without_a_boot_image_is_refused(self):
        with self.assertRaises(sd_card.ReleaseError):
            sd_card.open_release(make_zip(self.root, image=None))

    def test_a_damaged_zip_is_refused(self):
        path = os.path.join(self.root, '20260916.zip')
        with open(path, 'wb') as fh:
            fh.write(b'this is not a zip file')
        with self.assertRaises(sd_card.ReleaseError):
            sd_card.open_release(path)

    def test_installing_from_a_zip_copies_the_image_only(self):
        tool = make_tool(self.root)
        release = sd_card.open_release(make_zip(self.root, image=b'from the zip'))
        target, backup = release.install(tool)
        with open(target, 'rb') as fh:
            self.assertEqual(fh.read(), b'from the zip')
        self.assertIsNone(backup)
        self.assertEqual(sorted(os.listdir(sd_card.profile_folder(tool))), ['boot_image.sb'])

    def test_installing_from_a_zip_keeps_the_previous_image(self):
        tool = make_tool(self.root)
        sd_card.open_release(make_zip(self.root, '20250101.zip', '20250101/', b'old')).install(tool)
        _target, backup = sd_card.open_release(make_zip(self.root, image=b'new')).install(tool)
        with open(backup, 'rb') as fh:
            self.assertEqual(fh.read(), b'old')

    def test_a_huge_boot_image_is_refused_and_leaves_nothing_behind(self):
        tool = make_tool(self.root)
        path = os.path.join(self.root, '20260916.zip')
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('20260916/boot_image.sb', b'\0' * (sd_card.MAX_IMAGE_BYTES + 1))
        with self.assertRaises(sd_card.ReleaseError):
            sd_card.open_release(path).install(tool)
        self.assertEqual(os.listdir(sd_card.profile_folder(tool)), [])

    def test_a_folder_release_with_the_teams_double_folder(self):
        outer = os.path.join(self.root, '20260918')
        sb = make_release(outer, '20260918', data=b'in a folder', notes=['Folder note'])
        release = sd_card.open_release(outer)
        self.assertEqual((release.kind, release.date), ('folder', datetime.date(2026, 9, 18)))
        self.assertEqual(release.notes(), 'Folder note')
        tool = make_tool(self.root)
        target, _backup = release.install(tool)
        with open(target, 'rb') as fh:
            self.assertEqual(fh.read(), b'in a folder')
        self.assertTrue(os.path.isfile(sb))

    def test_a_folder_without_a_boot_image_is_refused(self):
        os.makedirs(os.path.join(self.root, '20260916'))
        with self.assertRaises(sd_card.ReleaseError):
            sd_card.open_release(os.path.join(self.root, '20260916'))

    def test_a_bare_sb_file_is_a_release(self):
        release = sd_card.open_release(make_release(self.root, '20260916', notes=['Bare note']))
        self.assertEqual((release.kind, release.date), ('file', datetime.date(2026, 9, 16)))
        self.assertEqual(release.notes(), 'Bare note')

    def test_find_releases_lists_the_newest_first_and_ignores_the_rest(self):
        make_zip(self.root, '20260916.zip', '20260916/')
        make_zip(self.root, '20260918.zip', '20260918/')
        make_release(os.path.join(self.root, '20250101'), '20250101')     # a folder with an image
        os.makedirs(os.path.join(self.root, 'empty folder'))
        with open(os.path.join(self.root, 'readme.txt'), 'w') as fh:
            fh.write('not a release')
        with open(os.path.join(self.root, 'broken.zip'), 'wb') as fh:
            fh.write(b'nope')
        names = [os.path.basename(r.path) for r in sd_card.find_releases(self.root)]
        self.assertEqual(names, ['20260918.zip', '20260916.zip', '20250101'])

    def test_same_content_is_not_fooled_by_equal_size_and_time(self):
        a, b = os.path.join(self.root, 'a'), os.path.join(self.root, 'b')
        for path, data in ((a, b'old image'), (b, b'new image')):        # same size, different bytes
            with open(path, 'wb') as fh:
                fh.write(data)
            os.utime(path, (1_700_000_000, 1_700_000_000))               # and the same time
        self.assertFalse(sd_card.same_content(a, b))
        self.assertFalse(sd_card.same_content(a, b))                      # asked again: still no
        with open(b, 'wb') as fh:
            fh.write(b'old image')
        self.assertTrue(sd_card.same_content(a, b))

    def test_a_different_image_of_the_same_size_replaces_the_old_one(self):
        tool = make_tool(self.root)
        first = make_release(self.root, '20250101', data=b'old image')
        second = make_release(self.root, '20260916', data=b'new image')
        for path in (first, second):
            os.utime(path, (1_700_000_000, 1_700_000_000))
        sd_card.install_image(first, tool)
        target, backup = sd_card.install_image(second, tool)
        with open(target, 'rb') as fh:
            self.assertEqual(fh.read(), b'new image')
        self.assertIsNotNone(backup)

    def test_find_releases_of_a_missing_folder_is_empty(self):
        self.assertEqual(sd_card.find_releases(os.path.join(self.root, 'nope')), [])


if __name__ == '__main__':
    unittest.main()
