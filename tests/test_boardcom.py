"""BoardComm: a board that does not answer must not leave the program in a Retry/Cancel loop
when the GUI asks for no dialog (start-up)."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dubLibs import boardcom  # noqa: E402


REPLY = b'ver 1.0' + bytes([13, 10]) + b'>>> '     # what the MCU sends back


class SilentPort:
    """A serial port the MCU never answers on"""
    timeout = 2

    def reset_input_buffer(self):
        pass

    def write(self, data):
        return len(data)

    def read_until(self, expected=b''):
        return b''


class TimeoutTests(unittest.TestCase):
    def comm(self):
        comm = boardcom.BoardComm()
        comm.handle = SilentPort()
        return comm

    def test_send_raises_instead_of_asking_when_the_dialog_is_off(self):
        comm = self.comm()
        comm.retryDialog = False
        with mock.patch.object(boardcom, 'askretrycancel') as dialog:
            with self.assertRaises(boardcom.BoardTimeout):
                comm.send('ver')
        dialog.assert_not_called()

    def test_send_asks_by_default_and_cancel_raises_instead_of_quitting(self):
        comm = self.comm()
        with mock.patch.object(boardcom, 'askretrycancel', return_value=False) as dialog:
            with self.assertRaises(boardcom.BoardTimeout):
                comm.send('ver')
        dialog.assert_called_once()
        text = dialog.call_args[0][1]
        for hint in ('RESET', 'SD card', 'MCU'):
            self.assertIn(hint, text)

    def test_retry_reads_again(self):
        comm = self.comm()
        answers = [b'', REPLY]
        comm.handle.read_until = lambda expected=b'': answers.pop(0)
        with mock.patch.object(boardcom, 'askretrycancel', return_value=True) as dialog:
            comm.send('ver')
        dialog.assert_called_once()

    def test_a_silent_board_keeps_the_short_timeout(self):
        comm = self.comm()
        comm.retryDialog = False
        with self.assertRaises(boardcom.BoardTimeout):
            comm.connectToMCU()
        self.assertEqual(comm.handle.timeout, 2)

    def test_the_first_answer_sets_the_long_timeout(self):
        comm = self.comm()
        comm.handle.read_until = lambda expected=b'': REPLY
        comm.send('ver')
        self.assertEqual(comm.handle.timeout, boardcom.LONG_TIMEOUT)

    def test_connect_does_not_pop_up_when_the_dialog_is_off(self):
        import serial
        comm = boardcom.BoardComm()
        comm.retryDialog = False
        with mock.patch.object(boardcom.serial, 'Serial', side_effect=serial.SerialException('busy')), \
                mock.patch.object(boardcom, 'askretrycancel') as dialog:
            self.assertIsNone(comm.connect('COM9'))
        dialog.assert_not_called()


if __name__ == '__main__':
    unittest.main()
