"""Where Help > Datasheet looks: the docs folder, the user's datasheet folder
(Documents, Dubrovnik, Datasheets), then the old place (a datasheets folder under the settings
folder in %APPDATA%, Dubrovnik).
Run:  python -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest

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
        self.real = settings.documents_folder
        settings.documents_folder = lambda: self.root       # never the real Documents
        self.addCleanup(setattr, settings, 'documents_folder', self.real)

    def test_the_folder_is_datasheets_in_documents_dubrovnik(self):
        self.assertEqual(settings.datasheet_folder(),
                         os.path.join(self.root, 'Dubrovnik', 'Datasheets'))

    def test_it_is_next_to_the_other_folders_of_the_user(self):
        self.assertEqual(os.path.dirname(settings.datasheet_folder()),
                         os.path.dirname(settings.default_folder('commandScripts')))

    def test_the_folder_is_not_made_by_asking_for_it(self):
        self.assertFalse(os.path.exists(settings.datasheet_folder()))

    def search(self, part='AT25SF641'):
        docs = os.path.join(self.root, 'docs')
        local = settings.datasheet_folder()                       # Documents, Dubrovnik, Datasheets
        settings_folder = os.path.join(self.root, 'roaming')      # its "datasheets" subfolder is the old place
        return docs, local, settings_folder, lambda: datasheet.find_local((docs, local, settings_folder), part)

    def test_a_datasheet_in_the_documents_folder_is_found(self):
        docs, local, old, find = self.search()
        path = touch(local, 'AT25SF641_datasheet.pdf')
        self.assertEqual(find(), path)

    def test_the_old_place_is_still_searched(self):
        docs, local, old, find = self.search()
        path = touch(os.path.join(old, 'datasheets'), 'AT25SF641_datasheet.pdf')
        self.assertEqual(find(), path)

    def test_the_order_is_docs_then_documents_then_old(self):
        docs, local, old, find = self.search()
        in_old = touch(os.path.join(old, 'datasheets'), 'AT25SF641_old.pdf')
        self.assertEqual(find(), in_old)
        in_local = touch(local, 'AT25SF641_documents.pdf')
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
