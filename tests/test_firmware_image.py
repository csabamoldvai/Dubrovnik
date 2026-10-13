"""Tests for dubLibs/firmware_image.py. Run:  python -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dubLibs import firmware_image as fi


def srec(kind, address, data):
    width = kind + 1
    body = bytes([width + len(data) + 1]) + address.to_bytes(width, 'big') + data
    return f'S{kind}{(body + bytes([~sum(body) & 0xFF])).hex().upper()}'


def ihex(kind, offset, data):
    body = bytes([len(data), offset >> 8, offset & 0xFF, kind]) + data
    return ':' + (body + bytes([-sum(body) & 0xFF])).hex().upper()


class SrecTests(unittest.TestCase):
    def test_s1_s2_s3(self):
        for kind, address in ((1, 0x1000), (2, 0x123456), (3, 0x12345678)):
            text = '\n'.join([srec(0, 0, b'hdr'), srec(kind, address, b'\x01\x02\x03'),
                              srec(9 - (kind - 1) * 0 if False else 9, 0, b'')])
            image = fi.parse_srec(text)
            self.assertEqual(image.segments, [(address, b'\x01\x02\x03')])

    def test_adjacent_records_merge_and_gap_stays(self):
        text = '\n'.join([srec(1, 0, b'ab'), srec(1, 2, b'cd'), srec(1, 0x100, b'ef')])
        image = fi.parse_srec(text)
        self.assertEqual(image.segments, [(0, b'abcd'), (0x100, b'ef')])
        self.assertEqual((image.size, image.start, image.end), (6, 0, 0x102))
        self.assertEqual(len(image.to_bytes()), 0x102)
        self.assertEqual(image.to_bytes()[4:6], b'\xff\xff')

    def test_checksum_error_has_line_number(self):
        bad = srec(1, 0, b'ab')[:-2] + '00'
        with self.assertRaisesRegex(fi.ImageError, 'line 2: checksum'):
            fi.parse_srec(srec(1, 0, b'x') + '\n' + bad)

    def test_count_record(self):
        good = '\n'.join([srec(1, 0, b'a'), srec(1, 4, b'b'), srec(5, 2, b'')[:0] or
                          'S5030002FA'])
        self.assertEqual(len(fi.parse_srec(good).segments), 2)
        with self.assertRaisesRegex(fi.ImageError, 'record count'):
            fi.parse_srec(srec(1, 0, b'a') + '\nS5030002FA')

    def test_conflicting_overlap(self):
        with self.assertRaisesRegex(fi.ImageError, 'conflicting'):
            fi.parse_srec('\n'.join([srec(1, 0, b'abcd'), srec(1, 2, b'XY')]))
        image = fi.parse_srec('\n'.join([srec(1, 0, b'abcd'), srec(1, 2, b'cd')]))
        self.assertEqual(image.segments, [(0, b'abcd')])


class IhexTests(unittest.TestCase):
    def test_extended_linear_and_segment(self):
        text = '\n'.join([ihex(4, 0, b'\x00\x01'), ihex(0, 0x10, b'\xAA\xBB'),
                          ihex(1, 0, b'')])
        self.assertEqual(fi.parse_ihex(text).segments, [(0x10010, b'\xAA\xBB')])
        text = '\n'.join([ihex(2, 0, b'\x10\x00'), ihex(0, 0x20, b'\xCC'),
                          ihex(1, 0, b'')])
        self.assertEqual(fi.parse_ihex(text).segments, [(0x10020, b'\xCC')])

    def test_start_records_ignored_and_errors(self):
        text = '\n'.join([ihex(0, 0, b'\x01'), ihex(5, 0, b'\x00\x00\x00\x00'),
                          ihex(1, 0, b'')])
        self.assertEqual(fi.parse_ihex(text).size, 1)
        bad = ihex(0, 0, b'\x01')[:-2] + '00'
        with self.assertRaisesRegex(fi.ImageError, 'line 1: checksum'):
            fi.parse_ihex(bad)
        with self.assertRaisesRegex(fi.ImageError, 'after the end'):
            fi.parse_ihex('\n'.join([ihex(1, 0, b''), ihex(0, 0, b'\x01')]))


class DetectionTests(unittest.TestCase):
    def test_detection(self):
        s, h = srec(1, 0, b'a').encode(), ihex(0, 0, b'a').encode()
        self.assertEqual(fi.parse_image(s, 'x.bin').kind, 'binary')   # .bin wins
        self.assertEqual(fi.parse_image(s, 'x.dat').kind, 'S-record')
        self.assertEqual(fi.parse_image(h + b'\n' + ihex(1, 0, b'').encode(), 'x.dat').kind,
                         'Intel HEX')
        self.assertEqual(fi.parse_image(b'\x00\x01\x02', 'x.dat').segments,
                         [(0, b'\x00\x01\x02')])
        self.assertEqual(fi.parse_image(b'\xef\xbb\xbf' + s, 'x.srec').size, 1)

    def test_wrong_extension_still_explains(self):
        with self.assertRaises(fi.ImageError):
            fi.parse_image(b'garbage text\n', 'x.srec')
        with self.assertRaises(fi.ImageError):
            fi.parse_image(b'', 'x.bin')

    def test_load_image_and_describe(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'a.s19')
            with open(path, 'w') as fh:
                fh.write(srec(1, 0x10, b'abc') + '\n')
            image = fi.load_image(path)
            self.assertIn('S-record: 1 segment, 3 bytes, 0x10 to 0x12', image.describe())


if __name__ == '__main__':
    unittest.main()
