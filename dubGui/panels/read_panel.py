"""The Read panel: read flash contents into the Terminal."""
from tkinter import DISABLED, E, EW, NW, StringVar, W
from tkinter import ttk
from tkinter.messagebox import showerror
import customtkinter as ctk
from dubGui.look import ENTRY_HEIGHT, RADIO_STYLE
from dubGui.panels.base import LabeledFrame
from dubLibs import hexdump
from dubLibs.fields import parseField


class ReadFrame(LabeledFrame):
    def __init__(self, parent, app, DEBUG=False):
        LabeledFrame.__init__(self, parent, text='Read')
        self.app = app
        self.DEBUG = DEBUG
        self.comm = None
        self.spiMode = StringVar()
        self.startAddr = StringVar()
        self.readLength = StringVar()
        self.spiModes = ['SPI', 'Dual',
                         'Quad (114)', 'Quad (144)', 'QPI (444)', 'Octal']
        self.buildFrame()
        self.spiMode.set(self.spiModes[0])

    def buildFrame(self):
        '''Makes a reusable frame for a flash read operation'''
        rb1_read = ctk.CTkRadioButton(self, **RADIO_STYLE, text=self.spiModes[0],
                                      variable=self.spiMode, value=self.spiModes[0])
        rb1_read.grid(row=1, column=0, padx=10, pady=2, sticky=W)
        rb2_read = ctk.CTkRadioButton(self, **RADIO_STYLE, text=self.spiModes[1],
                                      variable=self.spiMode, value=self.spiModes[1])
        rb2_read.grid(row=2, column=0, padx=10, pady=2, sticky=W)
        rb3_read = ctk.CTkRadioButton(self, **RADIO_STYLE, text=self.spiModes[2],
                                      variable=self.spiMode, value=self.spiModes[2])
        rb3_read.grid(row=3, column=0, padx=10, pady=2, sticky=W)
        rb4_read = ctk.CTkRadioButton(self, **RADIO_STYLE, text=self.spiModes[3],
                                      variable=self.spiMode, value=self.spiModes[3])
        rb4_read.grid(row=4, column=0, padx=10, pady=2, sticky=W)
        rb5_read = ctk.CTkRadioButton(self, **RADIO_STYLE, text=self.spiModes[4],
                                      variable=self.spiMode, value=self.spiModes[4],
                                      state=DISABLED)  # not supported yet
        rb5_read.grid(row=5, column=0, padx=10, pady=2, sticky=W)
        rb6_read = ctk.CTkRadioButton(self, **RADIO_STYLE, text=self.spiModes[5],
                                      variable=self.spiMode, value=self.spiModes[5],
                                      state=DISABLED)  # not supported yet
        rb6_read.grid(row=6, column=0, padx=10, pady=2, sticky=NW)

        lbl_read = ctk.CTkLabel(self, text='Start Address:  0x')
        lbl_read.grid(row=1, column=1, padx=10, pady=2, sticky=E)
        ent1_read = ctk.CTkEntry(self, textvariable=self.startAddr, width=80, height=ENTRY_HEIGHT)
        ent1_read.grid(row=1, column=2, padx=(0, 10), sticky=EW)

        self.startAddr.set('0')
        self.readLength.set('200')

        lbl2_read = ctk.CTkLabel(self, text='Length:  0x')
        lbl2_read.grid(row=2, column=1, padx=10, pady=2, sticky=E)
        ent2_read = ctk.CTkEntry(self, textvariable=self.readLength, width=80, height=ENTRY_HEIGHT)
        ent2_read.grid(row=2, column=2, padx=(0, 10), sticky=EW)

        dispmode_lbl = ctk.CTkLabel(self, text='Display Mode: ')
        dispmode_lbl.grid(row=5, column=1, padx=5, sticky="E")

        # add "HexView (h)": 'h'}
        self.dispmodeOptions = {"Binary (b)": 'b', "DWord (w)": 'w',
                                "Hex Dump (h)": 'h'}
        options = list(self.dispmodeOptions.keys())
        # Same kind of box as the COM port list (ttk, styled by styleCombobox),
        # so both have the same arrow, colours and font.
        self.dispmode_cb = ttk.Combobox(
            self, width=10, values=options, state='readonly',
            font=ctk.CTkFont().create_scaled_tuple(self._get_widget_scaling()))
        self.dispmode_cb.bind('<<ComboboxSelected>>', self.dispmode_cb_updated)
        self.dispmode_cb.grid(row=5, column=2, padx=(0, 10), sticky=EW)

        self.dispmode_cb.set(options[0])
        self.app.du.dispmode = self.dispmodeOptions[options[0]]

        btn1_read = ctk.CTkButton(self, text='Read', width=80,
                                  command=self.readFlash)
        btn1_read.grid(row=6, column=2, padx=(0, 10), sticky='sew', pady=(2, 10))
        self.grid_rowconfigure(6, weight=1)    # button row sits at the panel bottom

        if self.DEBUG:
            btn2_read = ctk.CTkButton(self, text='Read test',
                                      width=90, command=self.readFlash)
            btn2_read.grid(row=6, column=1, padx=2, pady=2)

    def applyDispMode(self, label):
        """Selects a display mode (a key of dispmodeOptions) in the combo box"""
        self.dispmode_cb.set(label)
        self.app.du.dispmode = self.dispmodeOptions[label]

    def dispmode_cb_updated(self, _choice=None):
        dispModeSelKey = self.dispmode_cb.get()  # get the selected item in Combo
        # assign the associated value to dispmode
        mode = self.dispmodeOptions[dispModeSelKey]
        self.app.du.dispmode = mode  # update dispmode in class Dubrovnik
        self.dispmode_cb.set(dispModeSelKey)
        self.app.settings.dispMode = self.dispmode_cb.get()    # remembered automatically
        self.app.settings.save()

    def readFlash(self):
        if self.app.serCom.scriptBusy():
            return
        if not self.app.serCom.checkConnection():  # check if board is connected
            return
        try:
            readStartAddr = parseField('Start Address', self.startAddr.get())
            readLen = parseField('Length', self.readLength.get())
        except ValueError as e:
            showerror('Read', str(e))
            return
        # print(f'SPI Mode      : {self.spiMode.get()}')
        # print(f'Start Address : {readStartAddr}')
        # print(f'Read Lenght   : {readLen}')
        try:
            self.app.du.read_mode(self.comm, self.spiMode.get(),
                         start_addr=readStartAddr, length=readLen, echo=0)
        except ValueError as e:
            showerror('Read', str(e))
            return
        text = self.app.du.textToDisplay[:-1]
        if self.app.du.dispmode == 'h':          # laid out here, like a hex editor
            data = hexdump.bytes_from_reply(
                self.app.du.textToDisplay, getattr(self.comm, 'cmdline', ''))
            if len(data) == readLen:
                text = hexdump.format_hexdump(
                    data, readStartAddr, per_row=self.app.settings.hexRow,
                    show_ascii=self.app.settings.hexAscii, upper=self.app.settings.hexUpper,
                    gap=self.app.settings.hexGap)
            else:
                text = (f'(Hex Dump: expected {readLen} bytes, found '
                        f'{len(data)}; raw reply follows)\n' + text)
        self.app.term.tprint(text, printOn='guiConsole')
