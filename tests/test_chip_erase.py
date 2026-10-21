"""Tests for the chip erase helpers: JEDEC density, time estimate, cancellable send.
Run:  python -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dubLibs import boardcom, dubrovnik


class FakePort:
    """Serial port that answers with `chunks`, one per read() call, then nothing"""
    def __init__(self, chunks):
        self.chunks, self.written, self.timeout = list(chunks), [], 5
        self.in_waiting = 0

    def reset_input_buffer(self):
        pass

    def write(self, data):
        self.written.append(data)
        return len(data)

    def read(self, n=1):
        return self.chunks.pop(0) if self.chunks else b''


class FakeComm:
    def __init__(self, reply):
        self.reply = reply

    def send(self, cmd):
        self.cmdline = cmd

    def response(self, removeCmd=False, removePrompt=True, returnAsList=False):
        return self.reply


class DensityTests(unittest.TestCase):
    def code(self, reply):
        return dubrovnik.Dubrovnik().read_density_code(FakeComm(reply))

    def test_third_byte_is_the_density_code(self):
        self.assertEqual(self.code('ef 40 18'), 0x18)

    def test_unreadable_reply_gives_none(self):
        self.assertIsNone(self.code('ef 40'))
        self.assertIsNone(self.code('ff ff ff'))

    def test_estimate_grows_with_capacity(self):
        est = dubrovnik.Dubrovnik.chip_erase_estimate_s
        self.assertLess(est(0x16), est(0x18))
        self.assertAlmostEqual(est(0x18) / est(0x17), 2)
        self.assertEqual(est(None), dubrovnik.CHIP_ERASE_DEFAULT_S)

    def test_16_mb_device_takes_about_84_seconds(self):
        # code 0x18 = 2**24 bytes; AT25SL128A measured 83.7 s
        self.assertAlmostEqual(dubrovnik.Dubrovnik.chip_erase_estimate_s(0x18), 84.5, delta=2)


class CancellableSendTests(unittest.TestCase):
    def comm(self, chunks):
        comm = boardcom.BoardComm()
        comm.handle = FakePort(chunks)
        return comm

    def test_done_when_the_prompt_arrives(self):
        comm = self.comm([b'06; c7', b' ok\r\n', b'>>> '])
        self.assertEqual(comm.send_cancellable('06; c7; wait 0', lambda: False), 'done')
        self.assertEqual(comm.handle.timeout, 5)            # restored

    def test_cancel_sends_ctrl_c_and_reports_the_prompt(self):
        comm = self.comm([b'x', b'x'])
        state = {'n': 0}

        def cancel():
            state['n'] += 1
            if state['n'] == 2:
                comm.handle.chunks.append(b'>>> ')          # board reacts to Ctrl+C
            return state['n'] >= 2
        self.assertEqual(comm.send_cancellable('c7', cancel), 'cancelled')
        self.assertIn(b'\x03', comm.handle.written)

    def test_cancel_with_a_busy_board(self):
        comm = self.comm([])
        self.assertEqual(comm.send_cancellable('c7', lambda: True, grace=0.2), 'busy')


if __name__ == '__main__':
    unittest.main()
