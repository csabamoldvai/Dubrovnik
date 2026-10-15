"""parseField: the check applied to every entry box of the panels."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dubLibs.fields import parseField  # noqa: E402


class ParseFieldTests(unittest.TestCase):
    def test_hex_is_the_default_base(self):
        self.assertEqual(parseField('Start Address', ' 1F00 '), 0x1F00)

    def test_decimal(self):
        self.assertEqual(parseField('Count', '12', base=10), 12)

    def test_num_blocks_is_hex(self):
        self.assertEqual(parseField('Num. Blocks', '1F'), 0x1F)

    def test_exact_digits(self):
        self.assertEqual(parseField('Pattern', 'caba0000', digits=8), 0xcaba0000)
        for bad in ('caba', 'caba00000', '0xcaba00', '-caba000', 'caba 000', 'cabag000'):
            with self.assertRaisesRegex(ValueError, 'must be exactly 8 hex digits'):
                parseField('Pattern', bad, digits=8)
        with self.assertRaisesRegex(ValueError, '"Pattern" is empty'):
            parseField('Pattern', '', digits=8)

    def test_empty_is_refused_with_the_field_name(self):
        with self.assertRaisesRegex(ValueError, '"Length" is empty'):
            parseField('Length', '   ')

    def test_not_a_number(self):
        with self.assertRaisesRegex(ValueError, 'not a valid hexadecimal number: xyz'):
            parseField('Offset', 'xyz')
        with self.assertRaisesRegex(ValueError, 'not a valid decimal number: 1F'):
            parseField('Count', '1F', base=10)

    def test_negative_only_when_signed(self):
        with self.assertRaisesRegex(ValueError, 'must not be negative'):
            parseField('Offset', '-1')
        self.assertEqual(parseField('Increment', '-1', signed=True), -1)


if __name__ == '__main__':
    unittest.main()
