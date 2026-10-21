"""Tests for the helper calls of the `dub` object (dubLibs/run_py_script.py).
Run:  python -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dubLibs import run_py_script as rp

MEMORY = bytes((i * 7) & 0xFF for i in range(0x3000))        # the pretend flash


class FakeComm:
    cmdline = ''


class FakeDu:
    """Stands in for the Dubrovnik library: reads come from MEMORY in the
    board's binary display mode (32 values per line)"""
    def __init__(self):
        self.dispmode = 'w'                  # the panel is set to Word
        self.textToDisplay = ''
        self.programmed = []
        self.modes_seen = []

    def read_mode(self, comm, mode, start_addr=0, length=0, echo=0):
        self.modes_seen.append(self.dispmode)
        comm.cmdline = f'0b {start_addr:x} {length:x}\r'
        data = MEMORY[start_addr:start_addr + length]
        rows = [' '.join(f'{b:02x}' for b in data[i:i + 32]) + ' '
                for i in range(0, len(data), 32)]
        self.textToDisplay = comm.cmdline + '\n' + '\r\n'.join(rows) + '\r\n>>> '

    def data_program(self, comm, data, address):
        self.programmed.append((address, bytes(data)))
        self.textToDisplay = 'programmed\n'
        return 100


class FakeTerm:
    comm = FakeComm()

    def scriptPrint(self, text):
        pass


def make_api(**kw):
    du = FakeDu()
    return rp.DubApi(FakeTerm(), du, lambda: None, lambda: False, **kw), du


def srec(address, data):
    body = bytes([5 + len(data)]) + address.to_bytes(4, 'big') + data
    return 'S3' + (body + bytes([~sum(body) & 0xFF])).hex().upper()


class ReadBytesTests(unittest.TestCase):
    def test_reads_exact_bytes_in_chunks_and_restores_the_display_mode(self):
        api, du = make_api()
        data = api.read_bytes(0x400, 0x2500, chunk=0x1000)
        self.assertEqual(data, MEMORY[0x400:0x400 + 0x2500])
        self.assertEqual(set(du.modes_seen), {'b'})          # forced to bytes
        self.assertEqual(du.dispmode, 'w')                   # panel setting back

    def test_wrong_byte_count_is_an_error(self):
        api, du = make_api()
        original = du.read_mode

        def short(comm, mode, start_addr=0, length=0, echo=0):
            original(comm, mode, start_addr, length - 1, echo)
        du.read_mode = short
        with self.assertRaisesRegex(rp.ScriptError, 'returned'):
            api.read_bytes(0, 16)
        self.assertEqual(du.dispmode, 'w')

    def test_stop_request_stops_a_long_read(self):
        du, calls = FakeDu(), []
        api = rp.DubApi(FakeTerm(), du, lambda: None, lambda: len(calls) > 2)
        du.read_mode = lambda *a, **k: calls.append(1) or FakeDu.read_mode(du, *a, **k)
        with self.assertRaises(rp.ScriptStopped):
            api.read_bytes(0, 0x3000, chunk=0x100)


class HexdumpTests(unittest.TestCase):
    def test_uses_the_panel_settings_and_options_override(self):
        api, _ = make_api(hex_options=lambda: dict(per_row=8, show_ascii=False,
                                                    upper=False, gap=False))
        self.assertEqual(api.hexdump(b'\xab\xcd', 0x10), '00000010  ab cd')
        self.assertIn('AB CD', api.hexdump(b'\xab\xcd', 0x10, upper=True))

    def test_defaults_without_settings(self):
        api, _ = make_api()
        self.assertTrue(api.hexdump(b'AB', 0).endswith('|AB|'))


class ImageTests(unittest.TestCase):
    def test_load_and_program_image_with_offset(self):
        api, du = make_api()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'fw.srec')
            with open(path, 'w') as fh:
                fh.write(srec(0x2000, b'abcd') + '\n' + srec(0x9000, b'xy') + '\n')
            image = api.load_image(path)
            self.assertEqual(image.size, 6)
            total = api.program_image(image, offset=0x10)
            self.assertEqual(du.programmed, [(0x2010, b'abcd'), (0x9010, b'xy')])
            self.assertEqual(total, 200)
            du.programmed.clear()
            api.program_image(path)                           # a path works too
            self.assertEqual(du.programmed[0][0], 0x2000)

    def test_bad_files_are_script_errors(self):
        api, _ = make_api()
        with self.assertRaises(rp.ScriptError):
            api.load_image(os.path.join(tempfile.gettempdir(), 'no_such_file.srec'))
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'bad.srec')
            with open(path, 'w') as fh:
                fh.write('S3xx\n')
            with self.assertRaisesRegex(rp.ScriptError, 'line 1'):
                api.load_image(path)


class VerifyTests(unittest.TestCase):
    def test_match_and_mismatch(self):
        api, _ = make_api()
        self.assertEqual(api.verify(0x100, MEMORY[0x100:0x180]), [])
        wrong = bytearray(MEMORY[0x100:0x180])
        wrong[3] ^= 0xFF
        wrong[100] ^= 0x01
        found = api.verify(0x100, bytes(wrong))
        self.assertEqual([a for a, _, _ in found], [0x103, 0x164])
        self.assertEqual(found[0], (0x103, wrong[3], MEMORY[0x103]))
        self.assertEqual(len(api.verify(0, bytes(255 - b for b in MEMORY[:100]),
                                        limit=5)), 5)


if __name__ == '__main__':
    unittest.main()
