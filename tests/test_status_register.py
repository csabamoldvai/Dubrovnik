"""Tests for reading and writing status register 2 on devices with different command tables
(the board's own "help <opcode>" says what each command is).
Run:  python -m unittest discover -s tests"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dubLibs import dubrovnik

ERROR = 'Error: invalid arguments'

# What "help 35", "help 5", "help 31" and "help 1" print on the devices seen so far
STANDARD = {          # AT25SF641: 35 reads STS2, 05 takes no count
    '35': 'Read Status Register-2                                      35',
    '5': 'Read Status Register-1                                      05',
    '31': 'Write Status Register-2 :                                  31 <data>',
    '1': 'Write Status Register-1 (and optionally 2) :               01 <data> <data>',
}
LOCKDOWN = {          # 35 is something else; STS2 comes with 05 2
    '35': 'Read Sector Lockdown Registers                             35 <address>',
    '5': 'Read Status Register 1                                     05 <count>',
    '31': 'Write Status Register 2 :                                  31 <data>',
    '1': 'Write Status Register 1 :                                  01 <data>',
}
BOTH_AT_ONCE = {      # no 31: 01 <sts1> <sts2> writes both
    '35': 'Read Status Register 2                                      35',
    '5': 'Read Status Register 1                                     05',
    '31': '',
    '1': 'Write Status Register-1 (and optionally 2) :               01 <data> <data>',
}


class FakeBoard:
    """Answers like the Tiberias board for the commands the status register code uses.
    helps: the help texts; has35: the device answers 35 with STS2; count: 05 wants a count."""

    def __init__(self, helps, has35=True, count=False, sts1=0x00, sts2=0x00):
        self.helps, self.has35, self.count = helps, has35, count
        self.sts1, self.sts2 = sts1, sts2
        self.sent, self.reply, self.cmdline = [], '', ''

    def send(self, cmd):
        self.sent.append(cmd)
        self.cmdline = cmd
        self.reply = self.answer(cmd)

    def response(self, removeCmd=False, removePrompt=True, returnAsList=False):
        return self.reply

    def answer(self, cmd):
        if cmd.startswith('help '):
            return self.helps[cmd.split()[1]]
        if cmd == '35':
            return f'{self.sts2:02x}' if self.has35 else ERROR
        if cmd == '05':
            return ERROR if self.count else f'{self.sts1:02x}'
        if cmd == '05 1':
            return f'{self.sts1:02x}' if self.count else ERROR
        if cmd == '05 2':
            return f'{self.sts1:02x} {self.sts2:02x}' if self.count else ERROR
        parts = [p.strip() for p in cmd.split(';')]
        if parts[0] == '06':                 # write enable, then the write
            match = re.fullmatch(r'31 ([0-9a-f]{2})', parts[1])
            if match:
                self.sts2 = int(match.group(1), 16)
            match = re.fullmatch(r'01 ([0-9a-f]{2}) ([0-9a-f]{2})', parts[1])
            if match:
                self.sts1, self.sts2 = int(match.group(1), 16), int(match.group(2), 16)
            return ''
        return ERROR


def helps_sent(board):
    return [c for c in board.sent if c.startswith('help ')]


class ReadTests(unittest.TestCase):
    def setUp(self):
        self.du = dubrovnik.Dubrovnik()

    def test_standard_device_reads_with_35(self):
        board = FakeBoard(STANDARD, sts2=0x02)
        self.assertEqual(self.du.read_status2(board), 0x02)
        self.assertIn('35', board.sent)
        self.assertNotIn('05 2', board.sent)

    def test_device_without_35_reads_with_05_2_and_takes_the_last_byte(self):
        board = FakeBoard(LOCKDOWN, has35=False, count=True, sts1=0x1c, sts2=0x42)
        self.assertEqual(self.du.read_status2(board), 0x42)
        self.assertIn('05 2', board.sent)
        self.assertNotIn('35', board.sent)         # it would have been an error

    def test_help_is_asked_once_per_connection(self):
        board = FakeBoard(LOCKDOWN, has35=False, count=True)
        for _ in range(3):
            self.du.read_status2(board)
        self.assertEqual(len(helps_sent(board)), 4)

    def test_forget_asks_again(self):
        board = FakeBoard(STANDARD)
        self.du.read_status2(board)
        self.du.forget_status_forms()
        self.du.read_status2(board)
        self.assertEqual(len(helps_sent(board)), 8)

    def test_a_new_connection_object_asks_again(self):
        self.du.read_status2(FakeBoard(STANDARD))
        board = FakeBoard(LOCKDOWN, has35=False, count=True, sts2=0x02)
        self.assertEqual(self.du.read_status2(board), 0x02)
        self.assertIn('05 2', board.sent)

    def test_hyphen_or_space_in_the_help_text(self):
        for text in ('Read Status Register-2   35', 'read status register 2   35',
                     'Read Status Register  2   35'):
            du = dubrovnik.Dubrovnik()
            board = FakeBoard(dict(LOCKDOWN, **{'35': text}), count=True, sts2=0x02)
            self.assertEqual(du.read_status2(board), 0x02, text)
            self.assertNotIn('05 2', board.sent, text)

    def test_unclear_help_keeps_35(self):
        board = FakeBoard({'35': '', '5': '', '31': '', '1': ''}, sts2=0x02)
        self.assertEqual(self.du.read_status2(board), 0x02)

    def test_a_bad_reply_names_the_command_and_the_reply(self):
        board = FakeBoard(STANDARD, has35=False)
        with self.assertRaises(ValueError) as caught:
            self.du.read_status2(board)
        self.assertIn('35', str(caught.exception))
        self.assertIn('invalid arguments', str(caught.exception))

    def test_a_bad_reply_makes_it_ask_again(self):
        board = FakeBoard(STANDARD, has35=False)
        with self.assertRaises(ValueError):
            self.du.read_status2(board)
        self.assertIsNone(self.du.stsForms)


class QuadEnableTests(unittest.TestCase):
    def setUp(self):
        self.du = dubrovnik.Dubrovnik()

    def test_standard_device_writes_with_31(self):
        board = FakeBoard(STANDARD, sts2=0x00)
        self.du.set_quad_enable(board, True)
        self.assertEqual(board.sts2, 0x02)
        self.assertIn('06; 31 02; wait 0', board.sent)

    def test_device_without_35_enables_and_clears_quad(self):
        board = FakeBoard(LOCKDOWN, has35=False, count=True, sts1=0x1c, sts2=0x00)
        self.du.set_quad_enable(board, True)
        self.assertEqual(board.sts2, 0x02)
        self.du.set_quad_enable(board, False)
        self.assertEqual(board.sts2, 0x00)

    def test_no_write_when_the_bit_is_already_right(self):
        board = FakeBoard(STANDARD, sts2=0x02)
        self.du.set_quad_enable(board, True)
        self.assertFalse([c for c in board.sent if c.startswith('06')])

    def test_other_bits_of_sts2_are_kept(self):
        board = FakeBoard(STANDARD, sts2=0x40)
        self.du.set_quad_enable(board, True)
        self.assertEqual(board.sts2, 0x42)

    def test_device_without_31_writes_both_registers_and_keeps_sts1(self):
        board = FakeBoard(BOTH_AT_ONCE, sts1=0x1c, sts2=0x00)
        self.du.set_quad_enable(board, True)
        self.assertEqual((board.sts1, board.sts2), (0x1c, 0x02))
        self.assertIn('06; 01 1c 02; wait 0', board.sent)

    def test_both_registers_with_a_counted_05(self):
        helps = dict(BOTH_AT_ONCE, **{'5': 'Read Status Register 1   05 <count>'})
        board = FakeBoard(helps, count=True, sts1=0x1c, sts2=0x00)
        self.du.set_quad_enable(board, True)
        self.assertEqual((board.sts1, board.sts2), (0x1c, 0x02))
        self.assertIn('05 1', board.sent)

    def test_a_write_that_does_not_stick_is_reported(self):
        board = FakeBoard(STANDARD, sts2=0x00)
        board.answer = lambda cmd, real=board.answer: ('' if cmd.startswith('06') else real(cmd))
        with self.assertRaises(ValueError):
            self.du.set_quad_enable(board, True)

    def test_set_quad_enable_says_what_it_changed(self):
        board = FakeBoard(STANDARD, sts2=0x40)
        self.assertEqual(self.du.set_quad_enable(board, True), (0x40, 0x42))
        self.assertIsNone(self.du.set_quad_enable(board, True))              # already set
        self.assertEqual(self.du.set_quad_enable(board, False), (0x42, 0x40))


class QuadEnableNoteTests(unittest.TestCase):
    """read_mode leaves a one-line note in du.notes when it changes the Quad Enable bit (the Read
    panel and the scripts show it); textToDisplay stays the board's data only"""

    def setUp(self):
        self.du = dubrovnik.Dubrovnik()
        self.du.read = lambda *args, **kwargs: 'data'       # the read itself is not under test

    def test_a_quad_read_that_sets_the_bit_leaves_a_note(self):
        board = FakeBoard(STANDARD, sts2=0x00)
        self.du.read_mode(board, 'Quad (114)')
        self.assertEqual(self.du.notes,
                         ['(Quad Enable set: status register 2 was 00, now 02)'])

    def test_an_spi_read_that_clears_the_bit_leaves_a_note(self):
        board = FakeBoard(STANDARD, sts2=0x02)
        self.du.read_mode(board, 'SPI')
        self.assertEqual(self.du.notes,
                         ['(Quad Enable cleared: status register 2 was 02, now 00)'])

    def test_no_note_when_the_bit_was_already_right(self):
        self.du.read_mode(FakeBoard(STANDARD, sts2=0x02), 'Quad (114)')
        self.assertEqual(self.du.notes, [])
        self.du.read_mode(FakeBoard(STANDARD, sts2=0x00), 'Dual')
        self.assertEqual(self.du.notes, [])

    def test_the_note_is_for_one_read_only(self):
        board = FakeBoard(STANDARD, sts2=0x00)
        self.du.read_mode(board, 'Quad (114)')
        self.assertEqual(len(self.du.notes), 1)
        self.du.read_mode(board, 'Quad (114)')                # the bit is set now: nothing changes
        self.assertEqual(self.du.notes, [])

    def test_the_note_is_not_put_in_the_data_that_is_parsed(self):
        board = FakeBoard(STANDARD, sts2=0x00)
        self.du.textToDisplay = 'unchanged'
        self.du.read_mode(board, 'Quad (114)')
        self.assertEqual(self.du.textToDisplay, 'unchanged')   # the stubbed read left it alone

    def test_a_bit_that_does_not_stick_gives_an_error_and_no_note(self):
        board = FakeBoard(STANDARD, sts2=0x00)
        board.answer = lambda cmd, real=board.answer: ('' if cmd.startswith('06') else real(cmd))
        with self.assertRaises(ValueError):
            self.du.read_mode(board, 'Quad (114)')
        self.assertEqual(self.du.notes, [])

    def no_device_board(self):
        """A board with no flash device: it knows no status register command at all"""
        board = FakeBoard(STANDARD)
        board.answer = lambda cmd: 'Error: command not recognized'
        return board

    def test_no_device_the_read_goes_ahead_with_a_note(self):
        reads = []
        self.du.read = lambda *args, **kwargs: reads.append(args) or 'data'
        for mode in ('SPI', 'Dual', 'Quad (114)', 'Quad (144)'):
            reads.clear()
            self.du.read_mode(self.no_device_board(), mode)
            self.assertEqual(len(reads), 1, mode)
            self.assertEqual(len(self.du.notes), 1, mode)
            self.assertIn('Quad Enable not checked', self.du.notes[0])
            self.assertIn('flash device in the socket', self.du.notes[0])

    def test_no_device_the_status_error_names_the_likely_cause(self):
        with self.assertRaises(dubrovnik.StatusRegisterUnavailable) as caught:
            self.du.read_status2(self.no_device_board())
        self.assertIn('flash device in the socket', str(caught.exception))
        self.assertIsInstance(caught.exception, ValueError)         # scripts that catch it still work

    def test_no_device_the_board_is_asked_again_next_time(self):
        board = self.no_device_board()
        self.du.read_mode(board, 'SPI')
        self.assertIsNone(self.du.stsForms)

    def test_another_odd_reply_is_still_an_error(self):
        board = FakeBoard(STANDARD)
        board.answer = lambda cmd: (STANDARD[cmd.split()[1]] if cmd.startswith('help ') else 'garbage??')
        with self.assertRaises(ValueError) as caught:
            self.du.read_mode(board, 'SPI')
        self.assertNotIsInstance(caught.exception, dubrovnik.StatusRegisterUnavailable)
        self.assertEqual(self.du.notes, [])

    def test_an_unsupported_mode_clears_the_old_note(self):
        self.du.notes = ['old']
        with self.assertRaises(ValueError):
            self.du.read_mode(FakeBoard(STANDARD), 'Octal')
        self.assertEqual(self.du.notes, [])


if __name__ == '__main__':
    unittest.main()
