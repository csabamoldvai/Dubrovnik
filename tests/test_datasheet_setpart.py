"""The board's answer to the setpart command tells which part it works with now; the Workbench
shows it in the status bar so that Help > Datasheet looks for that part.
Run:  python -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dubLibs import datasheet


class SetpartReplyTests(unittest.TestCase):
    def test_the_part_comes_out_in_upper_case(self):
        self.assertEqual(datasheet.part_from_setpart('Changing target part to at25sl128a'), 'AT25SL128A')

    def test_a_part_that_is_already_upper_case(self):
        self.assertEqual(datasheet.part_from_setpart('Changing target part to ATXP064'), 'ATXP064')

    def test_surrounding_text_and_line_ends_are_ignored(self):
        self.assertEqual(datasheet.part_from_setpart('changing target part to atxp128\r\n>>> '), 'ATXP128')

    def test_a_refused_setpart_gives_nothing(self):
        self.assertEqual(datasheet.part_from_setpart('Error: invalid arguments'), '')

    def test_empty_and_none_give_nothing(self):
        self.assertEqual(datasheet.part_from_setpart(''), '')
        self.assertEqual(datasheet.part_from_setpart(None), '')

    def test_the_result_is_what_the_status_bar_text_is_read_back_as(self):
        status = 'COM9    115200 8N1    Device: ' + datasheet.part_from_setpart('Changing target part to at25sl128a')
        self.assertEqual(datasheet.part_from_status(status), 'AT25SL128A')

    def test_the_part_found_matches_a_datasheet_file_name(self):
        part = datasheet.part_from_setpart('Changing target part to at25sl128a')
        self.assertEqual(datasheet._candidates(part)[-1], 'at25sl128')      # the family spelling


if __name__ == '__main__':
    unittest.main()
