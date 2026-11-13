"""The script folders, Results and Assistant all start in the same Documents folder
(settings.documents_folder), so a redirected Documents (OneDrive) cannot split them.
Run:  python -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dubLibs import run_py_script as rp
from dubLibs import settings


class DocumentsFolderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.real = settings.documents_folder
        settings.documents_folder = lambda: self.temp.name
        self.addCleanup(setattr, settings, 'documents_folder', self.real)

    def test_the_script_folders_and_results_share_one_documents_folder(self):
        self.assertEqual(rp.documents_dir(), self.temp.name)
        self.assertEqual(settings.default_folder('commandScripts'),
                         os.path.join(self.temp.name, 'Dubrovnik', 'commandScripts'))
        api = rp.DubApi.__new__(rp.DubApi)          # output_path does not use the object
        path = api.output_path('r.txt')
        self.assertEqual(path, os.path.join(self.temp.name, 'Dubrovnik', 'Results', 'r.txt'))
        self.assertTrue(os.path.isdir(os.path.dirname(path)))


class RealDocumentsFolderTests(unittest.TestCase):
    def test_it_is_an_existing_folder(self):
        self.assertTrue(os.path.isdir(settings.documents_folder()))


if __name__ == '__main__':
    unittest.main()
