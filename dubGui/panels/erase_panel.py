"""The Erase panel: erase blocks of the flash."""
from tkinter import E, SW, StringVar, W
from tkinter.messagebox import showerror
import customtkinter as ctk
from dubGui.look import ENTRY_HEIGHT, RADIO_STYLE
from dubGui.panels.base import LabeledFrame
from dubLibs.fields import parseField


class EraseFrame(LabeledFrame):
    def __init__(self, parent, app, DEBUG=False):
        LabeledFrame.__init__(self, parent, text='Erase')
        self.app = app
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

        lbl2_ers = ctk.CTkLabel(self, text='Num. Blocks:    ')
        lbl2_ers.grid(row=2, column=1, padx=10, pady=2, sticky=E)
        ent2_ers = ctk.CTkEntry(self, textvariable=self.numBlocks, width=80, height=ENTRY_HEIGHT)
        ent2_ers.grid(row=2, column=2, padx=(0, 10), sticky=W)

        self.numBlocks.set('3')

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
        if self.app.serCom.scriptBusy():
            return
        if not self.app.serCom.checkConnection():  # check if board is connected
            return
        blkSzStr = self.blockSize.get().lower()
        try:
            start_addr = parseField('Start Address', self.startAddr.get())
            num_blocks = parseField('Num. Blocks', self.numBlocks.get(), base=10)
        except ValueError as e:
            showerror('Erase', str(e))
            return

        if blkSzStr != 'chip':  # if it is a '4','32' or '64
            block_size = int(blkSzStr)
            blockSizeKB = block_size * 1024
            startAddr = (start_addr // blockSizeKB) * blockSizeKB
            self.app.term.tprint(f'Erasing {num_blocks} {block_size}kB block(s) from address {startAddr:x}',
                        printOn='guiConsole')
            self.app.du.block_erase(
                self.comm, block_size, start_addr, num_blocks)
        else:
            self.app.term.tprint('Erasing chip', printOn='guiConsole')
            self.app.du.block_erase(self.comm, blkSzStr)

        self.app.term.tprint(self.app.du.textToDisplay[:-1])

    def erase_test(self):
        print(f'Selected Erase Block Size : {self.blockSize.get()}')
        print(f'Start Address             : {self.startAddr.get()}')
        print(f'Number of Blocks          : {self.numBlocks.get()}')
        print('\n')
