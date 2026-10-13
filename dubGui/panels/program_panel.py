"""The Program panel: program the flash from a pattern or from a firmware file."""
import os
from tkinter import DISABLED, E, NORMAL, S, SW, StringVar, W
from tkinter.filedialog import askopenfilename
from tkinter.messagebox import showerror
import customtkinter as ctk
from dubGui.dialogs import messages
from dubGui.dialogs.progress import ProgramCancelled, ProgressDialog
from dubGui.look import ENTRY_HEIGHT, PAL, RADIO_STYLE
from dubGui.panels.base import LabeledFrame
from dubLibs import firmware_image, hexdump
from dubLibs.fields import parseField

PREVIEW_BYTES = 64         # Terminal preview of a loaded file: bytes per segment
PREVIEW_FULL = 1024        # segments up to this size are shown in full
PREVIEW_SEGMENTS = 8       # ... for the first few segments


class ProgramFrame(LabeledFrame):
    startAddr = 0
    dataLen = 0
    endAddr = 0
    pattn = 'cafe0000'
    incr = '1'
    image = None            # firmware_image.Image loaded with Open
    imageName = ''

    def __init__(self, parent, app, DEBUG=False):
        LabeledFrame.__init__(self, parent, text='Program')
        self.app = app
        self.DEBUG = DEBUG
        self.start_addr = StringVar()
        self.length = StringVar()
        self.pattern = StringVar()
        self.increment = StringVar()
        self.progModeVar = StringVar()
        self.progModeList = ['pattern', 'file']
        self.comm = None
        self.buildFrame()
        # set up the inital values in the frame
        self.progModeVar.set(self.progModeList[0])

    def buildFrame(self):
        '''Makes a reusable frame for a flash program operation'''
        rb_file = ctk.CTkRadioButton(self, **RADIO_STYLE, text='Use Pattern', variable=self.progModeVar,
                                     value=self.progModeList[0], command=self.grayOutEntry)
        rb_file.grid(row=2, column=0, padx=10, pady=2, sticky=W)

        rb_pattn = ctk.CTkRadioButton(self, **RADIO_STYLE, text='Load from File', variable=self.progModeVar,
                                      value=self.progModeList[1], command=self.grayOutEntry)
        rb_pattn.grid(row=3, column=0, padx=10, pady=2, sticky=W)

        lbl1_prog = self.lbl1_prog = ctk.CTkLabel(self, text='Pattern: 0x')
        lbl1_prog.grid(row=1, column=1, padx=5, pady=5, sticky=E)
        self.ent1_prog = ctk.CTkEntry(self, textvariable=self.pattern, width=80, height=ENTRY_HEIGHT)
        self.ent1_prog.grid(row=1, column=2, padx=(0, 10))
        self.pattern.set('caba0000')

        lbl2_prog = self.lbl2_prog = ctk.CTkLabel(self, text='Increment: 0x')
        lbl2_prog.grid(row=2, column=1, padx=5, pady=5, sticky=E)
        self.ent2_prog = ctk.CTkEntry(self, textvariable=self.increment, width=80, height=ENTRY_HEIGHT)
        self.ent2_prog.grid(row=2, column=2, padx=(0, 10))
        self.increment.set('1')

        lbl3_prog = self.lbl3_prog = ctk.CTkLabel(self, text='Start Address: 0x')
        lbl3_prog.grid(row=3, column=1, padx=5, pady=5, sticky=E)
        self.ent3_prog = ctk.CTkEntry(self, textvariable=self.start_addr, width=80, height=ENTRY_HEIGHT)
        self.ent3_prog.grid(row=3, column=2, padx=(0, 10))
        self.start_addr.set('60')

        lbl4_prog = self.lbl4_prog = ctk.CTkLabel(self, text='Length: 0x')
        lbl4_prog.grid(row=4, column=1, padx=5, pady=5, sticky=E)
        self.ent4_prog = ctk.CTkEntry(self, textvariable=self.length, width=80, height=ENTRY_HEIGHT)
        self.ent4_prog.grid(row=4, column=2, padx=(0, 10))
        self.length.set('250')

        self.btn_openFile = ctk.CTkButton(
            self, text='Open', width=80, command=self.openFile, state=DISABLED)
        self.btn_openFile.grid(row=6, column=0, padx=4, sticky=S, pady=(2, 10))
        self.btn_progFile = ctk.CTkButton(
            self, text='Program', width=80, command=self.program)
        self.btn_progFile.grid(row=6, column=1, padx=4, sticky=S, pady=(2, 10))
        self.grid_rowconfigure(6, weight=1)    # button row sits at the panel bottom
        self.btn_progVer = ctk.CTkButton(self, text='Prog/Verify',
                                         width=80, command=self.progVerify, state=DISABLED)
        self.btn_progVer.grid(row=6, column=2, padx=(0, 10), sticky=SW, pady=(2, 10))

    def get_states(self):
        global startAddr
        global dataLen
        global endAddr
        global pattn
        global incr
        pattern_mode = self.progModeVar.get() == 'pattern'
        s_addr = parseField('Start Address' if pattern_mode else 'Offset',
                            self.start_addr.get())
        d_len = parseField('Length', self.length.get()) if pattern_mode else 0
        if pattern_mode:
            parseField('Pattern', self.pattern.get())
            parseField('Increment', self.increment.get(), signed=True)
        startAddr, dataLen = s_addr, d_len
        endAddr = startAddr + dataLen
        pattn = self.pattern.get().strip()
        incr = self.increment.get().strip()

    def grayOutEntry(self):
        """Pattern mode uses Pattern, Increment, Start Address and Length; file
        mode uses only the Offset (the Start Address entry) and Open. What a mode
        does not use is greyed out, labels included."""
        fileMode = self.progModeVar.get() == 'file'
        unused = ((self.lbl1_prog, self.ent1_prog), (self.lbl2_prog, self.ent2_prog),
                  (self.lbl4_prog, self.ent4_prog))
        for label, entry in unused:
            if fileMode:
                label.configure(text_color=PAL['text_disabled'])
                entry.configure(state=DISABLED, fg_color=PAL['panel'],
                                text_color=PAL['text_disabled'])
            else:
                label.configure(text_color=PAL['text'])
                entry.configure(state=NORMAL, fg_color=PAL['entry'],
                                text_color=PAL['text'])
        self.btn_openFile.configure(state=NORMAL if fileMode else DISABLED)
        self.lbl3_prog.configure(
            text='Offset: 0x' if fileMode else 'Start Address: 0x')

    def program(self):
        if self.app.serCom.scriptBusy():
            return
        if not self.app.serCom.checkConnection():  # check if board is connected
            return
        try:
            self.get_states()
        except ValueError as e:
            showerror('Program', str(e))
            return
        if self.progModeVar.get() == 'pattern':
            self.app.du.page_program(
                self.comm, startAddr, dataLen, pattn, incr)
            self.app.term.tprint(self.app.du.textToDisplay[:-1])
            # term.displayText(du.textToDisplay)
        else:   # if programming a content of a file
            if self.image is None:
                showerror('Program', 'No file is loaded. Click Open first.')
                return
            if self.image.end + startAddr > 0xFFFFFFFF:
                showerror('Program', 'The address offset puts the data beyond '
                          'the 32-bit address range.')
                return
            self.programFile(startAddr)

    def programFile(self, offset):
        """Programs the loaded image segment by segment (the gaps between
        segments are left alone) at file address + offset. The work runs in a
        background thread so the window stays responsive; this method returns
        at once and the progress window is fed from a timer. Cancel (or Esc)
        stops between pages and leaves the device partly programmed."""
        import queue
        import threading
        segments = list(self.image.segments)
        count = len(segments)
        total = self.image.size
        state = dict(text='Starting...', done=0, cancel=False)
        messages = queue.Queue()        # Terminal text, shown from the GUI thread
        result = dict(finished=False, cancelled=False, error=None)
        comm = self.comm

        def work():
            """Background thread: talks to the board, never touches widgets"""
            try:
                base = 0
                for number, (address, data) in enumerate(segments, 1):
                    target = address + offset
                    where = f'segment {number} of {count}, ' if count > 1 else ''
                    messages.put(('displayText', f'Programming at 0x{target:X} '
                                  f'({len(data)} bytes)...\n'))

                    def progress(n, b=base, w=where, t=target):
                        if state['cancel']:
                            raise ProgramCancelled()
                        state['text'] = f'Programming, {w}address {t:X}'
                        state['done'] = b + n
                    self.app.du.data_program(comm, data, target, progress)
                    messages.put(('tprint', self.app.du.textToDisplay[:-1]))
                    base += len(data)
                result['finished'] = True
            except ProgramCancelled:
                result['cancelled'] = True
            except BaseException as e:      # incl. SystemExit from a comm error
                result['error'] = f'{type(e).__name__}: {e}'

        dialog = ProgressDialog(self.app.root, 'Programming', total)
        self.app.serCom.scriptRunning = True     # blocks the panels and the Terminal
        self.app.term.cmdInProgress = True       # and the background serial reader
        self.app.scriptStop[0] = False           # Esc or a lost connection cancels too
        worker = threading.Thread(target=work, daemon=True)
        worker.start()

        def poll():
            while True:
                try:
                    kind, text = messages.get_nowait()
                except queue.Empty:
                    break
                getattr(self.app.term, kind)(text)
            if dialog.cancelled or self.app.scriptStop[0]:
                state['cancel'] = True
            dialog.show(state['text'], state['done'])
            if worker.is_alive():
                self.app.root.after(100, poll)
                return
            while not messages.empty():     # text posted just before the end
                kind, text = messages.get_nowait()
                getattr(self.app.term, kind)(text)
            self.app.term.cmdInProgress = False
            self.app.serCom.scriptRunning = False
            dialog.close()
            if result['cancelled']:
                self.app.term.displayText('*** Programming cancelled; the device may be '
                                 'partly programmed. ***\n')
            elif result['error']:
                self.app.term.displayText(f'*** Programming stopped: {result["error"]}. '
                                 'The device may be partly programmed. ***\n')
            elif count > 1:
                self.app.term.displayText(f'Programmed {count} segments, '
                                 f'{self.image.size} bytes in total.\n')
        self.app.root.after(100, poll)

    def progVerify(self):
        pass

    def openFile(self):
        folder = self.app.settings.programDir
        filename = askopenfilename(
            title='Select File to Program',
            initialdir=folder if os.path.isdir(folder) else os.getcwd(),
            filetypes=firmware_image.FILE_TYPES)
        if not filename:             # dialog cancelled
            return False
        self.app.settings.programDir = os.path.dirname(filename)   # start here next time
        self.app.settings.save()
        try:
            self.image = firmware_image.load_image(filename)
        except OSError as e:
            showerror('Open', f'Could not read the file:\n{e}')
            return False
        except firmware_image.ImageError as e:
            showerror('Open', f'{os.path.basename(filename)} is not a valid '
                      f'firmware image:\n{e}')
            return False
        self.imageName = os.path.basename(filename)
        self.announce()
        return True

    def rangesText(self, offset=0, limit=6):
        """The address ranges the loaded image occupies at this offset, one
        per line (long lists are shortened)"""
        lines = [f'  0x{a + offset:X} to 0x{a + offset + len(d) - 1:X}  '
                 f'({len(d)} bytes)' for a, d in self.image.segments]
        if len(lines) > limit:
            lines = lines[:limit] + [f'  ... and {len(lines) - limit} more']
        return '\n'.join(lines)

    def announce(self):
        """Tells the user what was loaded: a summary and a short preview in the
        Terminal (everything is in File > Firmware > View File...)"""
        try:
            offset = parseField('Offset', self.start_addr.get())
        except ValueError:
            offset = 0
        self.app.term.displayText(f'Loaded {self.imageName}: {self.image.describe()}\n')
        preview, _rows = hexdump.format_segments(
            self.image.segments, offset, limit=PREVIEW_BYTES,
            full_if_at_most=PREVIEW_FULL, max_segments=PREVIEW_SEGMENTS,
            **self.app.settings.hexOptions())
        self.app.term.displayText(preview + '\n')
        self.app.term.displayText(f'Addresses are where the data will be written (file '
                         f'address + Offset 0x{offset:X}). Firmware > View File '
                         'shows everything. Erase first if needed.\n')
        self.app.showStatus(f'Loaded {self.imageName}: {self.image.describe()}', 8000)

    def closeFile(self):
        self.image, self.imageName = None, ''
