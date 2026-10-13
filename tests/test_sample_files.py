"""Tests with the sample files in tests/data (real firmware image and dumps).
Run:  python -m unittest discover -s tests"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from dubLibs import firmware_image as fi
from dubLibs import hexdump as hd

DATA = os.path.join(HERE, 'data')


def sample(name):
    return os.path.join(DATA, name)


class SrecSampleTests(unittest.TestCase):
    def test_test2_is_one_contiguous_block_from_0x2000(self):
        image = fi.load_image(sample('test2.srec'))
        self.assertEqual(image.kind, 'S-record')
        self.assertEqual([(a, len(d)) for a, d in image.segments], [(0x2000, 105901)])
        self.assertEqual((image.start, image.end), (0x2000, 0x1BDAD))

    def test_test1_is_a_sparse_sample_of_test2(self):
        small = fi.load_image(sample('test1.srec'))
        self.assertEqual([(a, len(d)) for a, d in small.segments],
                         [(0x2000, 48), (0x1BD80, 45)])
        full = fi.load_image(sample('test2.srec')).segments[0][1]
        for address, data in small.segments:
            start = address - 0x2000
            self.assertEqual(full[start:start + len(data)], data)

    def test_view_layout_of_a_real_file(self):
        small = fi.load_image(sample('test1.srec'))
        text, rows = hd.format_segments(small.segments, offset=0x100)
        lines = text.split('\n')
        self.assertTrue(lines[0].startswith('--- segment 1 of 2: 0x2100 to 0x212F (48 bytes)'))
        self.assertIn('gap of 105808 bytes before', text)
        self.assertTrue(lines[hd.line_for_address(rows, 0x1BE85) - 1].startswith('0001BE80'))


class OtherSampleTests(unittest.TestCase):
    def test_binary_sample_is_one_segment_at_zero(self):
        image = fi.load_image(sample('a_bin_file.bin'))
        self.assertEqual((image.kind, image.start, image.size), ('binary', 0, 1832))

    def test_binary_sample_is_the_text_sample_as_utf8(self):
        with open(sample('a_text_file.txt'), 'r', encoding='utf-8') as fh:
            text = fh.read()                       # text mode: CRLF becomes LF
        self.assertEqual(fi.load_image(sample('a_bin_file.bin')).segments[0][1],
                         text.encode('utf-8'))

    def test_memory_dump_text(self):
        with open(sample('memcontent.txt')) as fh:
            data = hd.bytes_from_reply(fh.read())
        self.assertEqual(len(data), 2048)
        self.assertEqual(data[:1024], b''.join(i.to_bytes(4, 'little') for i in range(256)))
        self.assertEqual(data[1024:], b'\xff' * 1024)        # erased half


class Text2BinTests(unittest.TestCase):
    def test_converter(self):
        import tempfile
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'dubUtils'))
        import text2bin_file
        with tempfile.TemporaryDirectory() as folder:
            out = text2bin_file.text_to_bin(sample('a_text_file.txt'),
                                            os.path.join(folder, 'x.bin'))
            with open(out, 'rb') as fh:
                self.assertEqual(fh.read(),
                                 fi.load_image(sample('a_bin_file.bin')).segments[0][1])


if __name__ == '__main__':
    unittest.main()
