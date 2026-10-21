"""The Erase panel: erase blocks of the flash."""
import queue
import threading
import time
from tkinter import E, SW, StringVar, W
from tkinter.messagebox import showerror
import customtkinter as ctk
from dubGui.dialogs.progress import ProgressDialog
from dubGui.look import ENTRY_HEIGHT, RADIO_STYLE
from dubGui.panels.base import LabeledFrame
from dubGui.tooltip import Tooltip
from dubLibs.dubrovnik import MEASURED_ERASE_S
from dubLibs.fields import parseField


class EraseFrame(LabeledFrame):
    def __init__(self, parent, serCom, term, du, DEBUG=False):
        LabeledFrame.__init__(self, parent, text='Erase')
        self.serCom = serCom        # the connection panel: is the board free and connected?
        self.term = term
        self.du = du                # the board library object
        self.DEBUG = DEBUG
        self.comm = None
        self.pageSize = 0x100
        self.blockSize = StringVar()
        self.startAddr = StringVar()
        self.numBlocks = StringVar()
        self.blockSizes = ['4', '32', '64', 'Chip']
        self.buildFrame()
        self.blockSize.set(self.blockSizes[0])

    def buildFrame(self):
        '''Makes a reusable frame for a flash erase operation'''
        rb1_ers = ctk.CTkRadioButton(self, **RADIO_STYLE, text='4kB',
                                     variable=self.blockSize, value=self.blockSizes[0])
        rb1_ers.grid(row=1, column=0, padx=10, pady=2, sticky=W)
        rb2_ers = ctk.CTkRadioButton(self, **RADIO_STYLE, text='32kB',
                                     variable=self.blockSize, value=self.blockSizes[1])
        rb2_ers.grid(row=2, column=0, padx=10, pady=2, sticky=W)
        rb3_ers = ctk.CTkRadioButton(self, **RADIO_STYLE, text='64kB',
                                     variable=self.blockSize, value=self.blockSizes[2])
        rb3_ers.grid(row=3, column=0, padx=10, pady=2, sticky=W)
        rb4_ers = ctk.CTkRadioButton(self, **RADIO_STYLE, text='Chip',
                                     variable=self.blockSize, value=self.blockSizes[3])
        rb4_ers.grid(row=4, column=0, padx=10, pady=2, sticky=W)

        lbl_ers = ctk.CTkLabel(self, text='Start Address:  0x')
        lbl_ers.grid(row=1, column=1, padx=10, pady=2, sticky=E)
        ent1_ers = ctk.CTkEntry(self, textvariable=self.startAddr, width=80, height=ENTRY_HEIGHT)
        ent1_ers.grid(row=1, column=2, padx=(0, 10), sticky=W)

        self.startAddr.set('0')
        Tooltip(ent1_ers, 'Hex digits only, no 0x. Example: 1000\n'
                'The block of the chosen size that contains this address is erased.')

        lbl2_ers = ctk.CTkLabel(self, text='Num. Blocks:  0x')
        lbl2_ers.grid(row=2, column=1, padx=10, pady=2, sticky=E)
        ent2_ers = ctk.CTkEntry(self, textvariable=self.numBlocks, width=80, height=ENTRY_HEIGHT)
        ent2_ers.grid(row=2, column=2, padx=(0, 10), sticky=W)

        self.numBlocks.set('3')
        Tooltip(ent2_ers, 'Hex digits only, no 0x. Example: 4')

        btn2_ers = ctk.CTkButton(self, text='Erase', width=80,
                                 command=self.blockErase)
        btn2_ers.grid(row=5, column=2, padx=(0, 10), sticky=SW, pady=(2, 10))
        self.grid_rowconfigure(5, weight=1)    # button row sits at the panel bottom

        if self.DEBUG:
            lbl4_ers = ctk.CTkLabel(self, text='Results here:')
            lbl4_ers.grid(row=5, column=0, sticky=E)

            quit_btn_ers = ctk.CTkButton(self, text='Erase test',
                                         width=90, command=self.erase_test)
            quit_btn_ers.grid(row=4, column=1, padx=2, pady=2)

    def blockErase(self):
        if self.serCom.scriptBusy():
            return
        if not self.serCom.checkConnection():  # check if board is connected
            return
        blkSzStr = self.blockSize.get().lower()
        try:
            start_addr = parseField('Start Address', self.startAddr.get())
            num_blocks = parseField('Num. Blocks', self.numBlocks.get())
        except ValueError as e:
            showerror('Erase', str(e))
            return

        if blkSzStr != 'chip':  # if it is a '4','32' or '64
            block_size = int(blkSzStr)
            blockSizeKB = block_size * 1024
            startAddr = (start_addr // blockSizeKB) * blockSizeKB
            self.term.tprint(f'Erasing 0x{num_blocks:x} {block_size}kB block(s) from address {startAddr:x}',
                        printOn='guiConsole')

            def blockDone(line):
                self.term.tprint(line)      # shown after each block, not at the end
                self.update_idletasks()
            self.du.block_erase(
                self.comm, block_size, start_addr, num_blocks, on_block=blockDone)
            self.term.tprint(self.du.textToDisplay[:-1])
        else:
            self.chipErase()

    def chipErase(self):
        """Chip erase with a progress window and a Cancel button. The erase runs in a
        background thread; this method returns at once and the window is fed from a
        timer. The bar is an estimate from the capacity of the device (JEDEC ID); it
        stops at 95 % until the board reports that the erase is finished."""
        messages = queue.Queue()        # Terminal text, shown from the GUI thread
        state = dict(cancel=False, expected=0, started=0.0)
        result = dict(error=None)
        comm = self.comm

        def work():
            """Background thread: talks to the board, never touches widgets"""
            try:
                jedec = self.du.read_jedec_id(comm)
                state['expected'] = self.du.chip_erase_estimate_s(jedec)
                if jedec not in MEASURED_ERASE_S and self.du.density_code(jedec) is None:
                    messages.put(('displayText', 'Capacity of the device not read from '
                                  'the JEDEC ID; the progress bar is a rough guess.\n'))
                if state['cancel']:         # Cancel while the capacity was read
                    self.du.eraseState = 'cancelled'
                    return
                state['started'] = time.time()
                self.du.chip_erase(comm, lambda: state['cancel'])
                messages.put(('tprint', self.du.textToDisplay[:-1]))
            except BaseException as e:      # incl. SystemExit from a comm error
                result['error'] = f'{type(e).__name__}: {e}'

        self.term.tprint('Erasing chip', printOn='guiConsole')
        self.du.eraseState = 'error'
        dialog = ProgressDialog(self.winfo_toplevel(), 'Chip Erase', 1000)
        self.serCom.scriptRunning = True     # blocks the panels and the Terminal
        self.term.cmdInProgress = True       # and the background serial reader
        worker = threading.Thread(target=work, daemon=True)
        worker.start()

        def poll():
            while True:
                try:
                    kind, text = messages.get_nowait()
                except queue.Empty:
                    break
                getattr(self.term, kind)(text)
            if dialog.cancelled:
                state['cancel'] = True
            elapsed = time.time() - state['started'] if state['started'] else 0
            if state['expected']:
                label = f'Erasing chip, expected about {state["expected"]:.0f} s'
                dialog.show(label, min(elapsed / state['expected'], 0.95) * 1000, remaining=False)
            else:
                dialog.show('Reading the device capacity...', 0)
            if worker.is_alive():
                self.after(100, poll)
                return
            while not messages.empty():     # text posted just before the end
                kind, text = messages.get_nowait()
                getattr(self.term, kind)(text)
            self.term.cmdInProgress = False
            self.serCom.scriptRunning = False
            dialog.close()
            if result['error']:
                self.term.displayText(f'*** Chip erase stopped: {result["error"]}. '
                                      'The device may be partly erased. ***\n')
            elif self.du.eraseState == 'cancelled':
                self.term.displayText('*** Chip erase cancelled; the device may be '
                                      'partly erased. ***\n')
            elif self.du.eraseState == 'busy':
                self.term.displayText('*** Chip erase cancelled, but the board did not '
                                      'answer yet: the device is probably still erasing. '
                                      'Wait for it to finish or power-cycle the board, '
                                      'press RESET and reconnect ***\n')
        self.after(100, poll)

    def erase_test(self):
        print(f'Selected Erase Block Size : {self.blockSize.get()}')
        print(f'Start Address             : {self.startAddr.get()}')
        print(f'Number of Blocks          : {self.numBlocks.get()}')
        print('\n')
