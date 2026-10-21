"""The Read panel: read flash contents into the Terminal."""
from tkinter import DISABLED, E, EW, NW, StringVar, W
from tkinter import ttk
from tkinter.messagebox import showerror
import customtkinter as ctk
from dubGui.look import ENTRY_HEIGHT, RADIO_STYLE
from dubGui.panels.base import LabeledFrame
from dubGui.tooltip import Tooltip
from dubLibs import hexdump
from dubLibs.fields import parseField

READ_CHUNK = 0x1000        # a longer read is done in pieces of this size (shown as they arrive)


class ReadFrame(LabeledFrame):
    def __init__(self, parent, serCom, term, du, settings, scriptStop, showStatus, DEBUG=False):
        LabeledFrame.__init__(self, parent, text='Read')
        self.serCom = serCom        # the connection panel: is the board free and connected?
        self.term = term
        self.du = du                # the board library object
        self.settings = settings
        self.scriptStop = scriptStop    # [bool]: Esc or a lost connection sets it
        self.showStatus = showStatus    # showStatus(text, ms): a message in the status bar
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
        Tooltip(ent1_read, 'Hex digits only, no 0x. Example: 0')

        lbl2_read = ctk.CTkLabel(self, text='Length:  0x')
        lbl2_read.grid(row=2, column=1, padx=10, pady=2, sticky=E)
        ent2_read = ctk.CTkEntry(self, textvariable=self.readLength, width=80, height=ENTRY_HEIGHT)
        ent2_read.grid(row=2, column=2, padx=(0, 10), sticky=EW)
        Tooltip(ent2_read, 'Hex digits only, no 0x, in bytes. Example: 100')

        dispmode_lbl = ctk.CTkLabel(self, text='Display Mode: ')
        dispmode_lbl.grid(row=5, column=1, padx=5, sticky="E")

        # add "HexView (h)": 'h'}
        self.dispmodeOptions = {"Byte": 'b', "Word": 'w', "Hex View": 'h'}
        options = list(self.dispmodeOptions.keys())
        # Same kind of box as the COM port list (ttk, styled by styleCombobox),
        # so both have the same arrow, colours and font.
        self.dispmode_cb = ttk.Combobox(
            self, width=10, values=options, state='readonly',
            font=ctk.CTkFont().create_scaled_tuple(self._get_widget_scaling()))
        self.dispmode_cb.bind('<<ComboboxSelected>>', self.dispmode_cb_updated)
        self.dispmode_cb.grid(row=5, column=2, padx=(0, 10), sticky=EW)

        self.dispmode_cb.set(options[0])
        self.du.dispmode = self.dispmodeOptions[options[0]]

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
        self.du.dispmode = self.dispmodeOptions[label]

    def dispmode_cb_updated(self, _choice=None):
        dispModeSelKey = self.dispmode_cb.get()  # get the selected item in Combo
        # assign the associated value to dispmode
        mode = self.dispmodeOptions[dispModeSelKey]
        self.du.dispmode = mode  # update dispmode in class Dubrovnik
        self.dispmode_cb.set(dispModeSelKey)
        self.settings.dispMode = self.dispmode_cb.get()    # remembered automatically
        self.settings.save()

    def readFlash(self):
        if self.serCom.scriptBusy():
            return
        if not self.serCom.checkConnection():  # check if board is connected
            return
        try:
            readStartAddr = parseField('Start Address', self.startAddr.get())
            readLen = parseField('Length', self.readLength.get())
        except ValueError as e:
            showerror('Read', str(e))
            return
        if readLen <= READ_CHUNK:
            try:
                text = self.readText(readStartAddr, readLen, True, self.spiMode.get())
            except ValueError as e:
                showerror('Read', str(e))
                return
            self.term.tprint(text, printOn='guiConsole')
        else:
            self.readLong(readStartAddr, readLen)

    def readText(self, start, length, first, spiMode):
        """Reads one piece from the board and returns the text for the Terminal: the
        board's reply, or in Hex View the hex-editor layout of it. first: this is
        the first piece of a read, so the echoed command is shown above it. (spiMode
        is passed in: a Tk variable must not be read in the background thread.)"""
        self.du.read_mode(self.comm, spiMode,
                          start_addr=start, length=length, echo=0)
        reply = self.du.textToDisplay
        cmdline = getattr(self.comm, 'cmdline', '')
        text = reply[:-1]
        if self.du.dispmode == 'h':          # laid out here, like a hex editor
            data = hexdump.bytes_from_reply(reply, cmdline)
            if len(data) != length:
                return (f'(Hex View: expected {length} bytes at 0x{start:X}, found '
                        f'{len(data)}; raw reply follows)\n' + text)
            text = hexdump.format_hexdump(
                data, start, per_row=self.settings.hexRow,
                show_ascii=self.settings.hexAscii, upper=self.settings.hexUpper,
                gap=self.settings.hexGap)
            if first:
                text = hexdump.echoed_command(reply, cmdline) + '\n' + text
        elif not first:                      # the echo of the command of each piece is noise
            command = cmdline.strip()
            lines = text.split('\n')
            if command and lines[0].strip().endswith(command):
                text = '\n'.join(lines[1:])
        return text

    def readLong(self, start, length):
        """A read of more than READ_CHUNK bytes: the board is asked piece by piece in a
        background thread and every piece is shown in the Terminal as soon as it has
        arrived. Esc stops it. The pieces end on multiples of READ_CHUNK, so in Hex
        View the rows line up from piece to piece."""
        import queue
        import threading
        messages = queue.Queue()        # Terminal text, shown from the GUI thread
        state = dict(cancel=False)
        result = dict(error=None, cancelled=False)
        spiMode = self.spiMode.get()

        def work():
            """Background thread: talks to the board, never touches widgets"""
            try:
                done = 0
                while done < length:
                    if state['cancel']:
                        result['cancelled'] = True
                        return
                    address = start + done
                    size = min(READ_CHUNK - address % READ_CHUNK, length - done)
                    messages.put(self.readText(address, size, done == 0, spiMode))
                    done += size
            except BaseException as e:      # incl. SystemExit from a comm error
                result['error'] = f'{type(e).__name__}: {e}'

        self.showStatus('Reading... press Esc to stop', 4000)
        self.serCom.scriptRunning = True     # blocks the panels and the Terminal
        self.term.cmdInProgress = True       # and the background serial reader
        self.scriptStop[0] = False
        worker = threading.Thread(target=work, daemon=True)
        worker.start()

        def poll():
            while True:
                try:
                    self.term.scriptPrint(messages.get_nowait())
                except queue.Empty:
                    break
            if self.scriptStop[0]:
                state['cancel'] = True
            if worker.is_alive():
                self.after(50, poll)
                return
            while not messages.empty():     # text posted just before the end
                self.term.scriptPrint(messages.get_nowait())
            self.term.cmdInProgress = False
            self.serCom.scriptRunning = False
            if result['cancelled']:
                self.term.scriptPrint('*** Read stopped. ***')
            elif result['error']:
                self.term.scriptPrint(f'*** Read stopped: {result["error"]} ***')
        self.after(50, poll)
