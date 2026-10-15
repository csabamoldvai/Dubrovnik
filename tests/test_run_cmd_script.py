import unittest
from dubLibs import run_cmd_script as rcs


class TestComments(unittest.TestCase):
    def test_split_comment(self):
        self.assertEqual(rcs.split_comment('freq 120  # set clock '), ('freq 120', 'set clock'))
        self.assertEqual(rcs.split_comment('freq 120'), ('freq 120', ''))
        self.assertEqual(rcs.split_comment('  # only a comment'), ('', 'only a comment'))
        self.assertEqual(rcs.split_comment('a # b # c'), ('a', 'b # c'))

    def test_parse_lines_keeps_comments_and_line_numbers(self):
        text = '# first\nconfig\n\nvolt 1.9 # core\n6; 31 2;  \n  # last\n'
        self.assertEqual(rcs.parse_lines(text), [
            (1, '', 'first'), (2, 'config', ''), (4, 'volt 1.9', 'core'),
            (5, '6; 31 2', ''), (6, '', 'last')])

    def test_parse_still_returns_only_commands(self):
        text = '# first\nconfig\n\nvolt 1.9 # core\n'
        self.assertEqual(rcs.parse(text), [(2, 'config'), (4, 'volt 1.9')])


if __name__ == '__main__':
    unittest.main()
