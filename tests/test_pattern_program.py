"""Tests for Dubrovnik.page_program: progress callback, cancel, log of pages.
Run:  python -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dubLibs import dubrovnik


class Comm:
    def __init__(self):
        self.sent = []

    def send(self, cmd):
        self.sent.append(cmd)


def make_du():
    du = dubrovnik.Dubrovnik()
    du.get_wait_time_us = lambda comm: 100
    return du


class PageProgramTests(unittest.TestCase):
    def test_progress_is_called_after_each_page(self):
        calls = []
        make_du().page_program(Comm(), 0x100, 0x2A0, progress=lambda *a: calls.append(a))
        self.assertEqual(calls, [(0x100, 1, 0x100), (0x200, 2, 0x200), (0x2A0, 3, 0x300)])

    def test_unaligned_start_ends_the_first_page_at_the_boundary(self):
        calls = []
        make_du().page_program(Comm(), 0x1F0, 0x20, progress=lambda *a: calls.append(a))
        self.assertEqual(calls, [(0x10, 1, 0x1F0), (0x20, 2, 0x200)])

    def test_progress_can_abort_between_pages(self):
        comm, count = Comm(), []

        def progress(done, page, address):
            count.append(page)
            if page == 2:
                raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            make_du().page_program(comm, 0, 0x1000, progress=progress)
        self.assertEqual(len(comm.sent), 1 + 2)             # pattern + two pages

    def test_a_line_per_page_by_default(self):
        du = make_du()
        du.page_program(Comm(), 0, 0x200)
        self.assertEqual(du.textToDisplay.count('page program time'), 2)
        self.assertIn('Total Program time', du.textToDisplay)

    def test_summary_instead_of_lines_for_large_runs(self):
        du = make_du()
        du.page_program(Comm(), 0, 0x10000, log_pages=False)
        self.assertNotIn('page program time', du.textToDisplay)
        self.assertIn('256 pages', du.textToDisplay)
        self.assertIn('slowest page', du.textToDisplay)
        self.assertIn('Total Program time: 25.600 ms', du.textToDisplay)


class ContinuousPatternTests(unittest.TestCase):
    @staticmethod
    def patterns(comm):
        return [c for c in comm.sent if c.startswith('pattern')]

    def test_default_sends_the_pattern_once(self):
        comm = Comm()
        make_du().page_program(comm, 0, 0x400, 'cafe0000', '1')
        self.assertEqual(self.patterns(comm), ['pattern cafe0000 1'])

    def test_continuous_sends_the_running_value_before_each_page(self):
        comm = Comm()
        make_du().page_program(comm, 0, 0x400, '00000000', '00010001', continuous=True)
        self.assertEqual(self.patterns(comm), ['pattern 00000000 00010001',
                                               'pattern 00400040 00010001',
                                               'pattern 00800080 00010001',
                                               'pattern 00c000c0 00010001'])

    def test_continuous_wraps_at_32_bits(self):
        comm = Comm()
        make_du().page_program(comm, 0, 0x200, 'ffffffc0', '1', continuous=True)
        self.assertEqual(self.patterns(comm)[1], 'pattern 00000000 1')

    def test_continuous_negative_increment(self):
        comm = Comm()
        make_du().page_program(comm, 0, 0x200, '00000040', '-1', continuous=True)
        self.assertEqual(self.patterns(comm)[1], 'pattern 00000000 -1')

    def test_continuous_partial_first_page_counts_the_words_used(self):
        comm = Comm()       # first page 0x1F0..0x1FF = 16 bytes = 4 words
        make_du().page_program(comm, 0x1F0, 0x110, '0', '1', continuous=True)
        self.assertEqual(self.patterns(comm), ['pattern 0 1', 'pattern 00000004 1'])


if __name__ == '__main__':
    unittest.main()
