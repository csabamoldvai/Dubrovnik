"""Tests for dubLibs/hexdump.py. Run:  python -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dubLibs import hexdump as hd


class FormatTests(unittest.TestCase):
    DATA = bytes.fromhex('00 00 02 20 19 70 10 03 37 71 00 00 73 79 00 00'
                         ' CB 79 00 00 97 A0 00 00')

    def test_two_rows_with_gap_and_ascii(self):
        lines = hd.format_hexdump(self.DATA, 0x2000).split('\n')
        self.assertEqual(lines[0], '00002000  00 00 02 20 19 70 10 03  37 71 00 00 73 79 00 00'
                                   '  |... .p..7q..sy..|')
        self.assertTrue(lines[1].startswith('00002010  CB 79 00 00 97 A0 00 00 '))
        self.assertTrue(lines[1].endswith('|.y......|'))
        self.assertEqual(len(lines), 2)

    def test_ascii_column_aligned_on_a_short_row(self):
        lines = hd.format_hexdump(self.DATA, 0).split('\n')
        self.assertEqual(lines[0].index('|'), lines[1].index('|'))

    def test_options(self):
        text = hd.format_hexdump(b'\xab\x41\x7f', 0x10, per_row=8, show_ascii=False,
                                 upper=False, gap=False)
        self.assertEqual(text, '00000010  ab 41 7f')
        wide = hd.format_hexdump(bytes(range(32)), 0, per_row=32, show_ascii=False)
        self.assertEqual(wide.count('  '), 1 + 3)            # after address + 3 gaps
        full = hd.format_hexdump(bytes(16), 0, show_ascii=False, gap=False)
        self.assertEqual(full.count('  '), 1)                # only after the address

    def test_unaligned_start_pads_the_first_row(self):
        text = hd.format_hexdump(b'AB', 0x2005, per_row=16, gap=True)
        self.assertTrue(text.startswith('00002000  ' + '   ' * 5 + '41 42'))
        self.assertIn('|     AB|', text)

    def test_rows_cross_an_unaligned_boundary(self):
        text = hd.format_hexdump(bytes(range(20)), 0xFC, per_row=16)
        self.assertEqual([ln[:8] for ln in text.split('\n')], ['000000F0', '00000100'])

    def test_empty_and_bad_row_size(self):
        self.assertEqual(hd.format_hexdump(b'', 0), '')
        with self.assertRaises(ValueError):
            hd.format_hexdump(b'a', 0, per_row=12)


class ReplyTests(unittest.TestCase):
    def test_board_reply(self):
        reply = ('0b 2000 40\r\n' + ' '.join(['00'] * 32) + ' \r\n'
                 + ' '.join(['ff'] * 32) + ' \r\n>>> ')
        data = hd.bytes_from_reply(reply, '0b 2000 40\r')
        self.assertEqual(data, bytes(32) + b'\xff' * 32)

    def test_command_that_looks_like_data_is_dropped(self):
        reply = '03 20 10\r\n11 22 33\r\n>>> '
        self.assertEqual(hd.bytes_from_reply(reply, '03 20 10\r'), b'\x11\x22\x33')

    def test_echoed_command(self):
        reply = '>>> 0b 2000 40\r\n' + ' '.join(['00'] * 32) + ' \r\n>>> '
        self.assertEqual(hd.echoed_command(reply, '0b 2000 40\r'), '>>> 0b 2000 40')
        self.assertEqual(hd.echoed_command('11 22\r\n', '0b 2000 2\r'), '0b 2000 2')
        self.assertEqual(hd.echoed_command('11 22\r\n', ''), '')

    def test_no_data_and_noise(self):
        self.assertEqual(hd.bytes_from_reply('Error: bad\r\n>>> ', 'x'), b'')
        self.assertEqual(hd.bytes_from_reply('11 22\r\nwhat\r\n33\r\n'), b'\x11\x22\x33')


if __name__ == '__main__':
    unittest.main()


class SegmentTests(unittest.TestCase):
    SEGS = [(0x2000, bytes(range(40))), (0x9000, b'xyz')]

    def test_headings_gaps_and_target_addresses(self):
        text, rows = hd.format_segments(self.SEGS, offset=0x10)
        lines = text.split('\n')
        self.assertTrue(lines[0].startswith('--- segment 1 of 2: 0x2010 to 0x2037 (40 bytes)'))
        self.assertIn('gap of', text)
        self.assertIn(f'gap of {0x9010 - 0x2038} bytes before', text)
        self.assertTrue(lines[1].startswith('00002010  '))

    def test_preview_limits(self):
        big = [(0, bytes(5000)), (0x10000, bytes(100)), (0x20000, b'a'), (0x30000, b'b')]
        text, rows = hd.format_segments(big, limit=64, full_if_at_most=1024,
                                        max_segments=3)
        self.assertIn('... 4936 more bytes', text)          # 5000 > 1024: cut to 64
        self.assertIn('00010060', text)                      # 100 <= 1024: shown in full
        self.assertEqual(text.count('more bytes'), 1)         # only the 5000-byte segment is cut
        self.assertIn('... and 1 more segments', text)

    def test_full_if_small(self):
        text, _ = hd.format_segments([(0, bytes(500))], limit=64, full_if_at_most=1024)
        self.assertNotIn('more bytes', text)
        self.assertEqual(text.count('\n'), 1 + 500 // 16)    # heading + 32 rows

    def test_line_for_address(self):
        text, rows = hd.format_segments(self.SEGS, offset=0)
        lines = text.split('\n')
        line = hd.line_for_address(rows, 0x2013)
        self.assertTrue(lines[line - 1].startswith('00002010'))
        self.assertTrue(lines[hd.line_for_address(rows, 0x9001) - 1].startswith('00009000'))
        # in the gap: the next row; beyond the end: the last row
        self.assertTrue(lines[hd.line_for_address(rows, 0x5000) - 1].startswith('00009000'))
        self.assertTrue(lines[hd.line_for_address(rows, 0xFFFFFF) - 1].startswith('00009000'))
        self.assertTrue(lines[hd.line_for_address(rows, 0) - 1].startswith('00002000'))
        self.assertIsNone(hd.line_for_address([], 5))
