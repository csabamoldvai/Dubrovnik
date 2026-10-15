"""find_tools: Python tools and command scripts of the Tools menu."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dubLibs.tools import find_tools  # noqa: E402


class FindToolsTests(unittest.TestCase):
    def make(self, files):
        folder = tempfile.mkdtemp()
        self.addCleanup(lambda: [os.remove(os.path.join(folder, f)) for f in os.listdir(folder)]
                        or os.rmdir(folder))
        for name, text in files.items():
            with open(os.path.join(folder, name), 'w', encoding='utf-8') as fh:
                fh.write(text)
        return folder

    def test_python_tools_come_first_then_command_scripts(self):
        folder = self.make({
            'a.txt': '# TOOL: Alpha script\nfreq 120\n',
            'b.py': 'x = 1\n# TOOL: Beta\n# DESCRIPTION: does b\n',
            'c.scr': '# tools: Charlie\nid\n',
            'd.py': '# TOOLS: Delta\n',
        })
        found = find_tools(folder)
        self.assertEqual([(t['name'], t['kind']) for t in found],
                         [('Beta', 'python'), ('Delta', 'python'),
                          ('Alpha script', 'command'), ('Charlie', 'command')])
        self.assertEqual(found[0]['description'], 'does b')

    def test_command_script_header_must_be_the_first_line(self):
        folder = self.make({'a.txt': 'id\n# TOOL: Late\n', 'b.txt': '\n# TOOL: Blank first\n',
                            'notes.md': '# TOOL: Wrong type\n', 'c.txt': '# TOOL:\nid\n'})
        self.assertEqual(find_tools(folder), [])


if __name__ == '__main__':
    unittest.main()
