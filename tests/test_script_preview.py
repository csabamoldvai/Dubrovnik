import unittest
from dubGui.dialogs.script_preview import numbered


class TestNumbered(unittest.TestCase):
    def test_numbers_every_line_including_blank_and_comment_lines(self):
        self.assertEqual(numbered('# a\nconfig\n\nvolt 1.9'),
                         '1  # a\n2  config\n3  \n4  volt 1.9')

    def test_numbers_line_up_when_there_are_ten_or_more_lines(self):
        lines = numbered('\n'.join(f'c{n}' for n in range(1, 11))).splitlines()
        self.assertEqual(lines[0], ' 1  c1')
        self.assertEqual(lines[9], '10  c10')


if __name__ == '__main__':
    unittest.main()
