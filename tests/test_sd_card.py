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


if __name__ == '__main__':
    unittest.main()
