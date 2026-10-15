"""BoardComm: a board that does not answer must not leave the program in a Retry/Cancel loop
when the GUI asks for no dialog (start-up)."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dubLibs import boardcom  # noqa: E402


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

    def test_send_still_asks_by_default_and_retries(self):
        comm = self.comm()
        with mock.patch.object(boardcom, 'askretrycancel', return_value=False) as dialog:
            with self.assertRaises(SystemExit):     # Cancel quits, as before
                comm.send('ver')
        dialog.assert_called_once()

    def test_connect_to_mcu_sets_the_long_timeout_even_when_the_board_is_silent(self):
        comm = self.comm()
        comm.retryDialog = False
        with self.assertRaises(boardcom.BoardTimeout):
            comm.connectToMCU()
        self.assertEqual(comm.handle.timeout, 200)

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
