"""Where Help > Datasheet looks: the docs folder, the datasheet folder of this PC
(%LOCALAPPDATA%\\Dubrovnik\\Datasheets), then the old place (a datasheets folder under the settings
folder in %APPDATA%\\Dubrovnik).
Run:  python -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dubLibs import datasheet, settings


def touch(folder, name):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    with open(path, 'wb') as fh:
        fh.write(b'%PDF-1.4')
    return path


class DatasheetFolderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name

    def test_the_folder_is_under_local_app_data(self):
        with mock.patch.dict(os.environ, {'LOCALAPPDATA': self.root}):
            self.assertEqual(settings.datasheet_folder(),
                             os.path.join(self.root, 'Dubrovnik', 'Datasheets'))

    def test_without_local_app_data_it_is_the_usual_place(self):
        env = {k: v for k, v in os.environ.items() if k != 'LOCALAPPDATA'}
        with mock.patch.dict(os.environ, env, clear=True):
            folder = settings.datasheet_folder()
        self.assertTrue(folder.endswith(os.path.join('AppData', 'Local', 'Dubrovnik', 'Datasheets')), folder)

    def test_the_folder_is_not_made_by_asking_for_it(self):
        with mock.patch.dict(os.environ, {'LOCALAPPDATA': self.root}):
            self.assertFalse(os.path.exists(settings.datasheet_folder()))

    def search(self, part='AT25SF641'):
        docs = os.path.join(self.root, 'docs')
        local = os.path.join(self.root, 'local')
        settings_folder = os.path.join(self.root, 'roaming')      # its "datasheets" subfolder is the old place
        return docs, local, settings_folder, lambda: datasheet.find_local((docs, local, settings_folder), part)

    def test_a_datasheet_in_the_local_folder_is_found(self):
        docs, local, old, find = self.search()
        path = touch(local, 'AT25SF641_datasheet.pdf')
        self.assertEqual(find(), path)

    def test_the_old_place_is_still_searched(self):
        docs, local, old, find = self.search()
        path = touch(os.path.join(old, 'datasheets'), 'AT25SF641_datasheet.pdf')
        self.assertEqual(find(), path)

    def test_the_order_is_docs_then_local_then_old(self):
        docs, local, old, find = self.search()
        in_old = touch(os.path.join(old, 'datasheets'), 'AT25SF641_old.pdf')
        self.assertEqual(find(), in_old)
        in_local = touch(local, 'AT25SF641_local.pdf')
        self.assertEqual(find(), in_local)
        in_docs = touch(docs, 'AT25SF641_docs.pdf')
        self.assertEqual(find(), in_docs)

    def test_nothing_found_is_empty(self):
        self.assertEqual(self.search()[3](), '')

    def test_a_missing_folder_is_skipped(self):
        docs, local, old, find = self.search()
        path = touch(os.path.join(old, 'datasheets'), 'AT25SF641.pdf')
        self.assertEqual(find(), path)       # docs and local do not exist at all


if __name__ == '__main__':
    unittest.main()
