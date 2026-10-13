# from dubGui.serialTerminalShell import Terminal
# import sys
# import time
import datetime
import os
import pathlib
import re
import sys
import tempfile
import webbrowser
from tkinter import (
    DISABLED, E, END, EW, INSERT, IntVar, Menu,
    NORMAL, NSEW, NW, S, SW, StringVar, W)
from tkinter import ttk
from tkinter.filedialog import askopenfilename, asksaveasfilename
from tkinter.messagebox import showerror, showwarning, showinfo
import customtkinter as ctk
from customtkinter.windows.widgets.scaling import ScalingTracker
# Use the dubLibs next to this project, not another copy found on PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dubLibs import boardcom
from dubLibs import run_cmd_script
from dubLibs import run_py_script
from dubLibs import tools
from dubLibs import datasheet
from dubLibs import documents
from dubLibs import firmware_image
from dubLibs import hexdump
from dubLibs import settings as settings_lib
from dubLibs.settings import Settings
from dubLibs import termstyle
from dubLibs.fields import parseField
from dubLibs.version import VERSION as APP_VERSION
from dubLibs import dubrovnik  # instead of "from dubLibs import Dubrovnik as du"
from dubGui.dialogs import messages
from dubGui.dialogs.assistant_window import AssistantWindow, ScriptReview
from dubGui.dialogs.file_viewer import FileViewer
from dubGui.dialogs.hex_dialog import HexDialog
from dubGui.dialogs.progress import ProgramCancelled, ProgressDialog
from dubGui.dialogs.terminal_dialog import TerminalDialog
from dubGui.look import (
    CHECKBOX_STYLE, ENTRY_HEIGHT, PAL, PANEL_BORDER, RADIO_STYLE, TERM_THEMES,
    styleCombobox, styleMenus)

PROMPT = '>>> '
CLEAR_CMD = 'clear'


def docsFolder():
    """Folder with the documents of the Help > Documents menu: inside the
    PyInstaller bundle when frozen, otherwise the project's docs folder"""
    base = getattr(sys, '_MEIPASS',
                   os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, 'docs')


def toolsFolder():
    """Folder with the Tools menu scripts: inside the PyInstaller bundle when
    frozen, otherwise the project's tools folder"""
    base = getattr(sys, '_MEIPASS',
                   os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, 'tools')


def defaultScriptDir():
    """Folder where the Run Script dialog starts the first time: the project's
    dubScripts folder if it exists, else the user's Documents folder"""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for folder in (os.path.join(here, 'dubScripts'),
                   os.path.join(os.path.expanduser('~'), 'Documents')):
        if os.path.isdir(folder):
            return folder
    return os.getcwd()


def helpFilePath():
    """Location of the HTML help file: inside the PyInstaller bundle when frozen,
    otherwise in the project's help folder"""
    base = getattr(sys, '_MEIPASS',
                   os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, 'help', 'dubrovnik_help.html')


def showHelp(_event=None):
    """Help > Help (F1): open the user guide in the default web browser"""
    path = helpFilePath()
    if not os.path.isfile(path):
        showerror('Help', f'The help file was not found: {path}')
        return
    # The help file holds @VERSION@ where the version number belongs. Fill it
    # in (from dubLibs/version.py) in a temporary copy that the browser opens.
    try:
        with open(path, encoding='utf-8') as fh:
            text = fh.read().replace('@VERSION@', APP_VERSION)
        shown = os.path.join(tempfile.gettempdir(), 'dubrovnik_help.html')
        with open(shown, 'w', encoding='utf-8') as fh:
            fh.write(text)
        path = shown
    except OSError:
        pass                        # fall back to the original file
    webbrowser.open(pathlib.Path(path).as_uri())


CFG_DEFAULTS = settings_lib.DEFAULTS   # see dubLibs/settings.py
TERM_SIZE_MIN, TERM_SIZE_MAX = termstyle.SIZE_MIN, termstyle.SIZE_MAX

# View > Menu text size: size in unscaled px of the menu bar and the pop-up
# menus (multiplied by the Windows display scaling)
MENU_SIZES = {'small': 12, 'normal': 14, 'large': 17}

TERM_MIN_LINES = 8   # minimum visible terminal lines when resizing the window

PREVIEW_BYTES = 64         # Terminal preview of a loaded file: bytes per segment
PREVIEW_FULL = 1024        # segments up to this size are shown in full
PREVIEW_SEGMENTS = 8       # ... for the first few segments


def hexOptions(serCom):
    """The View > Hex Dump settings (kept by serCom) as keyword arguments of hexdump"""
    return dict(per_row=serCom.hexRow, show_ascii=serCom.hexAscii,
                upper=serCom.hexUpper, gap=serCom.hexGap)


class LabeledFrame(ctk.CTkFrame):
    """CTkFrame with a title label at row 0 -- a stand-in for tk.LabelFrame.
    Subclasses should grid their content starting at row=1.
    """

    def __init__(self, master=None, text='', **kwargs):
        kwargs.setdefault('border_width', PANEL_BORDER)
        super().__init__(master, **kwargs)
        self._title = ctk.CTkLabel(
            self, text=text, anchor='w',
            font=ctk.CTkFont(weight='bold'))
        self._title.grid(row=0, column=0, columnspan=99,
                         padx=10, pady=(8, 4), sticky='w')

    def configure_title(self, text):
        self._title.configure(text=text)


class SerComFrame(LabeledFrame):
    def __init__(self, parent, app, DEBUG=False):
        LabeledFrame.__init__(self, parent, text='Serial Connection')
        self.app = app
        self.settings = app.settings          # the remembered settings (dubLibs/settings.py)
        self.DEBUG = DEBUG
        self.STANDALONE = False
        self.comm = None                      # object created by boardcom
        self.portStatus = 'disconnected'
        self.portList = []
        self.portHandle = None
        self.chk_var = IntVar()
        self.serParams = ''
        self.scriptRunning = False   # True while File > Run Script is running

        self.buildFrame()

    def buildFrame(self):
        '''Makes a reusable frame for a connecting to Dubrovnik board'''
        chk = ctk.CTkCheckBox(self, **CHECKBOX_STYLE, text='Auto connect', variable=self.chk_var)
        chk.grid(row=1, column=0, padx=10, pady=4)

        # ttk.Combobox kept here because CTkComboBox has no `postcommand`
        # (refresh-on-open) equivalent. Aesthetic gap is minor.
        # Same font as the CTk widgets next to it (their default font, scaled
        # the way CTk scales it, so the size matches at every Windows scaling).
        comboFont = ctk.CTkFont().create_scaled_tuple(self._get_widget_scaling())
        self.combo = ttk.Combobox(
            self, width=8, values=self.portList, font=comboFont,
            postcommand=self.updtPortList)
        self.option_add('*TCombobox*Listbox.font', comboFont)
        self.combo.grid(row=1, column=1, padx=10, pady=4)

        self.btn2 = ctk.CTkButton(self, text='Connect', width=100,
                                  command=self.connectPort)
        # Right-aligned: the panel is stretched to the Erase panel's width, and
        # the button's right edge then lines up with the Erase button's.
        self.btn2.grid(row=1, column=2, padx=10, pady=4, sticky=E)
        self.grid_columnconfigure(2, weight=1)

        if self.STANDALONE:
            self.btn3 = ctk.CTkButton(self, text='Save Config', width=100,
                                      command=self.saveConfig)
            self.btn3.grid(row=1, column=3, padx=10, pady=4, sticky=E)

        if self.DEBUG:
            self.test_btn = ctk.CTkButton(self, text='Testing', width=100,
                                          command=self.testSerComm)
            self.test_btn.grid(row=2, column=0, padx=5, pady=10, columnspan=1)
            self.test_lbl = ctk.CTkLabel(
                self, text="Debug message:", anchor='w')
            self.test_lbl.grid(row=2, column=1, padx=5,
                               pady=10, sticky=EW, columnspan=3)

    def updtPortList(self):
        self.portList = self.comm.findPorts(exit_if_none=False)
        self.combo['values'] = self.portList
        if self.portList:
            self.combo.set(self.portList[0])
        elif self.portStatus == 'disconnected':
            self.combo.set('')
            self.app.stsBarComm.configure(text='No COM port found: connect the USB cable, '
                             'turn on the board and press RESET')

    def connectPort(self, defaultPort=None, checkIsFlashPresent=True):
        if self.scriptBusy():
            return
        if self.portStatus == 'disconnected':
            if defaultPort:
                self.selPort = defaultPort         # updates class variable as well
                self.combo.set(self.selPort)
            else:
                self.selPort = self.combo.get()
            if not self.selPort:            # nothing chosen yet: look again
                self.updtPortList()
                self.selPort = self.combo.get()
            if not self.selPort:
                showwarning(
            'No board found',
            'No Dubrovnik board was found.\n\n1. Connect the USB cable\n'
            '2. Turn on the board\n3. Press the RESET button\n\n'
            'Then click Connect (the COM port list refreshes when you open it).')
                return
            # only if disconnected, connect to selected port
            self.portHandle = self.comm.connect(self.selPort)
            if self.portHandle is None:     # the port could not be opened
                self.app.stsBarComm.configure(text=f'Could not open {self.selPort}')
                return
            self.setSerialParams()
            self.btn2.configure(text='Disconnect')  # change button label
            self.portStatus = 'connected'  # update connection status
            self.serParams = f'Connected: {self.comPort} ({self.comBaudrate},{self.comBytesize},{self.comParity},{self.comStopbits},{self.comXonXoff})'
            if checkIsFlashPresent:  # allow this part to run only when enabled by func argument
                if self.comm.isFlashPresent():
                    pn = self.app.du.get_part_number(self.comm)
                    self.serParams += '    Device: ' + pn
            self.app.stsBarComm.configure(text=self.serParams)

        elif self.portStatus == 'connected':
            # if connected, disconnect from the current port
            self.disconnectPort(self.selPort)
            self.btn2.configure(text='Connect')  # update button label
            self.portStatus = 'disconnected'  # update connection status
            self.app.stsBarComm.configure(text='Disconnected')
        else:
            print('No such port. Try again!!!')
        self.saveConfig()

    def disconnectPort(self, selPort):
        self.comm.disconnect(selPort)
        # print(f"Port: {selPort} disconnected")
        self.app.stsBarComm.configure(text='No COM port found!')

    def scriptBusy(self):
        """True (with a message) while a script is running: the panels, the
        connection button and the Terminal command line are blocked meanwhile"""
        if self.scriptRunning:
            showinfo('Script', 'A script is running.\nPress Esc or choose '
                     'File > Stop Script to stop it.')
        return self.scriptRunning

    def checkConnection(self):
        """True if connected; otherwise shows a message and returns False"""
        if self.portStatus == 'disconnected':
            showerror('Dubrovnik Workbench Error',
                      'Unable to open COM port!\nConnect to the board')
            return False
        return True

    def connectionLost(self):
        """The board was switched off or unplugged: its COM port is gone.
        Closes the port and brings the window back to the disconnected state."""
        if self.portStatus != 'connected':
            return
        lost = self.selPort
        try:
            self.comm.disconnect(lost, echo=0)
        except Exception:
            pass                        # the port is gone anyway
        self.portStatus = 'disconnected'
        self.serParams = ''
        self.btn2.configure(text='Connect')
        self.app.stsBarComm.configure(text=f'Connection to {lost} lost: the board was '
                         'switched off or unplugged')
        self.app.term.displayText(f'*** Connection to {lost} lost (board switched off or '
                         'unplugged). Switch it on, press RESET and click '
                         'Connect. ***')
        if self.scriptRunning:          # a script can't go on without the board
            self.app.scriptStop[0] = True

    def deviceDetected(self, partNumber):
        """The board (re)detected its device, e.g. after being switched off and
        on again: show it in the status bar ('' = no device)"""
        if self.portStatus != 'connected':
            return
        base = self.serParams.split('    Device:')[0]
        self.serParams = base + (f'    Device: {partNumber}' if partNumber else '')
        self.app.stsBarComm.configure(text=self.serParams)

    def checkLink(self):
        """Every 2 s: is the COM port of the connected board still there?
        (Backs up the faster check in Terminal.pollSerial.)"""
        if self.portStatus == 'connected':
            try:
                present = self.selPort in self.comm.getPortList()
            except Exception:
                present = True          # can't tell: assume it is
            if not present:
                self.connectionLost()
        self.after(2000, self.checkLink)

    def setSerialParams(self):
        """ Gets serial communication port parameters """
        self.comPort = self.portHandle.port
        self.comBaudrate = self.portHandle.baudrate
        self.comBytesize = self.portHandle.bytesize
        self.comParity = self.portHandle.parity
        self.comStopbits = self.portHandle.stopbits
        self.comXonXoff = self.portHandle.xonxoff

    def loadDefaultParams(self):
        """Resets the entry boxes of the Erase, Program and Read panels"""
        self.app.erase.blockSize.set(self.app.erase.blockSizes[0])
        self.app.erase.startAddr.set('0')
        self.app.erase.numBlocks.set('1')
        self.app.program.pattern.set('cafe0000')
        self.app.program.increment.set('1')
        self.app.program.start_addr.set('0')
        self.app.program.length.set('100')
        self.app.read.spiMode.set(self.app.read.spiModes[0])
        self.app.read.startAddr.set('0')
        self.app.read.readLength.set('100')

    @property
    def selPort(self):
        """The port chosen last. It is also what is remembered as lastUsedPort"""
        return self.settings.lastUsedPort

    @selPort.setter
    def selPort(self, value):
        self.settings.lastUsedPort = value

    def loadDefaultSettings(self):
        """No usable settings file: the connection settings and the entry boxes
        start from their defaults (Settings.load has reset the settings)"""
        self.chk_var.set(0)
        self.loadDefaultParams()

    def paramValues(self):
        """The entry-box values of the Erase, Program and Read panels, in the
        form the settings file keeps them"""
        return {'eraseBlkSize': str(self.app.erase.blockSize.get()),
                'eraseStartAddr': str(self.app.erase.startAddr.get()),
                'eraseNumBlocks': str(self.app.erase.numBlocks.get()),
                'progPattern': self.app.program.pattern.get(),
                'progIncrement': self.app.program.increment.get(),
                'progStartAddr': self.app.program.start_addr.get(),
                'progLength': self.app.program.length.get(),
                'readSpiMode': self.app.read.spiMode.get(),
                'readStartAddr': self.app.read.startAddr.get(),
                'readLength': self.app.read.readLength.get()}

    def setParams(self, v):
        """Puts stored entry-box values (see paramValues) into the panels"""
        self.app.erase.blockSize.set(v['eraseBlkSize'])
        self.app.erase.startAddr.set(v['eraseStartAddr'])
        self.app.erase.numBlocks.set(v['eraseNumBlocks'])
        self.app.program.pattern.set(v['progPattern'])
        self.app.program.increment.set(v['progIncrement'])
        self.app.program.start_addr.set(v['progStartAddr'])
        self.app.program.length.set(v['progLength'])
        self.app.read.spiMode.set(v['readSpiMode'])
        self.app.read.startAddr.set(v['readStartAddr'])
        self.app.read.readLength.set(v['readLength'])

    def saveConfig(self, params=False):
        """Saves the settings that are remembered automatically (connection,
        window, ...). The entry-box values of the Erase, Program and Read
        panels are saved only when params=True (File > Parameters > Save);
        otherwise the values already stored in the file are kept."""
        self.settings.autoConnect = self.chk_var.get()
        self.settings.save(self.paramValues() if params else None)

    def loadConfig(self, prefs=True, params=True):
        """Loads the settings file: the remembered settings (prefs) and/or the
        stored entry-box values (params). A missing or damaged file, or a bad
        value in it, falls back to defaults; this never stops the app."""
        status, stored = self.settings.load(prefs=prefs, choices=dict(
            eraseBlkSize=self.app.erase.blockSizes,
            readSpiMode=self.app.read.spiModes,
            displayMode=tuple(self.app.read.dispmodeOptions),
            menuTextSize=tuple(MENU_SIZES)))
        if status == 'defaults':     # first run, or unreadable (kept as .bad)
            self.loadDefaultSettings()
            self.saveConfig(params=True)
            return
        if prefs:
            self.chk_var.set(self.settings.autoConnect)
            self.app.read.applyDispMode(self.settings.dispMode)
        if params:
            self.setParams(stored)

    def testSerComm(self):
        serParams = '%s, baud=%d, bytes=%1d,\nparity=%s, stop=%1d, protocol=%s' \
            % (self.comPort, self.comBaudrate, self.comBytesize, self.comParity, self.comStopbits, self.comXonXoff)
        self.test_lbl.configure(text=serParams)


def _forward(name):
    return property(lambda self: getattr(self.settings, name),
                    lambda self, value: setattr(self.settings, name, value))


# TEMPORARY: serCom.<setting> still works while the call sites are converted
for _name in ('appearance', 'autoConnect', 'datasheetUrl', 'dispMode', 'hexAscii', 'hexGap', 'hexRow', 'hexUpper', 'lastUsedPort', 'menuSize', 'programDir', 'scriptDir', 'showPanels', 'termBg', 'termFg', 'termFont', 'termFontSize', 'termSelect', 'termTheme', 'winPos', 'winSize', 'cfgFile'):
    setattr(SerComFrame, _name, _forward(_name))
SerComFrame.dubrovnikConfigPath = property(lambda self: self.settings.folder)


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
        folder = self.app.serCom.programDir
        filename = askopenfilename(
            title='Select File to Program',
            initialdir=folder if os.path.isdir(folder) else os.getcwd(),
            filetypes=firmware_image.FILE_TYPES)
        if not filename:             # dialog cancelled
            return False
        self.app.serCom.programDir = os.path.dirname(filename)   # start here next time
        self.app.serCom.saveConfig()
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
            **hexOptions(self.app.serCom))
        self.app.term.displayText(preview + '\n')
        self.app.term.displayText(f'Addresses are where the data will be written (file '
                         f'address + Offset 0x{offset:X}). Firmware > View File '
                         'shows everything. Erase first if needed.\n')
        self.app.showStatus(f'Loaded {self.imageName}: {self.image.describe()}', 8000)

    def closeFile(self):
        self.image, self.imageName = None, ''


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
        self.app.serCom.dispMode = self.dispmode_cb.get()    # remembered automatically
        self.app.serCom.saveConfig()

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
                    data, readStartAddr, per_row=self.app.serCom.hexRow,
                    show_ascii=self.app.serCom.hexAscii, upper=self.app.serCom.hexUpper,
                    gap=self.app.serCom.hexGap)
            else:
                text = (f'(Hex Dump: expected {readLen} bytes, found '
                        f'{len(data)}; raw reply follows)\n' + text)
        self.app.term.tprint(text, printOn='guiConsole')


class Terminal(LabeledFrame):
    def __init__(self, parent, app):
        LabeledFrame.__init__(self, parent, text='Terminal')
        self.app = app
        self.comm = None
        self.history = []
        self.historyIndex = 0
        # CM TODO: check if needed. displayText implemented differently
        self.textToDisplay = None
        # Async serial polling: set True while onReturnKey owns the serial port
        # so the poller doesn't race with comm.send()/response().
        self.cmdInProgress = False
        self.pollIntervalMs = 100

        self.txt = ctk.CTkTextbox(
            self, wrap='char', width=400, height=300,
            font=ctk.CTkFont(family='Consolas', size=15),
            border_width=0)
        self.onZoom = None       # set by the app: onZoom(+1 or -1), Ctrl + wheel
        self.applyColors(TERM_THEMES['dark'])
        self.txt.grid(row=1, column=0, columnspan=99,
                      pady=10, padx=10, sticky="NSEW")

        self.clear()
        self.txt.focus()      # placing cursor in text area

        # Key bindings
        self.txt.bind('<Return>', self.onReturnKey)
        self.txt.bind('<BackSpace>', self.onBackSpace)
        self.txt.bind('<Delete>', self.onDelete)
        self.txt.bind('<Up>', self.onUpArrowKey)
        self.txt.bind('<Down>', self.onDownArrowKey)
        self.txt.bind('<Left>', self.onLeftArrowKey)
        # Typing/pasting is only allowed on the active prompt line
        self.txt.bind('<Key>', self.onKeyPress)
        self.txt.bind('<<Paste>>', self.onPaste)
        self.txt.bind('<<Cut>>', lambda _e: 'break')
        # Ctrl + mouse wheel changes the text size instead of scrolling
        self.txt.bind('<Control-MouseWheel>', self.onCtrlWheel)

        # Right-click context menu
        self.ctxMenu = Menu(self.txt, tearoff=False)
        self.ctxMenu.add_command(label='Clear', command=self.clear)
        self.txt.bind('<Button-3>', self.showContextMenu)

        # Start the async serial poller. It runs forever and no-ops when the
        # port isn't open or a synchronous command is in progress.
        self.after(self.pollIntervalMs, self.pollSerial)

    def onCtrlWheel(self, event):
        if self.onZoom and event.delta:
            self.onZoom(1 if event.delta > 0 else -1)
        return 'break'          # no scrolling

    def setFont(self, family, size):
        self.txt.configure(font=ctk.CTkFont(family=family, size=size))

    def applyColors(self, t):
        """Sets the Terminal colours; t has the keys bg, fg and select"""
        self.txt.configure(fg_color=t['bg'], text_color=t['fg'])
        # tk.Text options CTkTextbox doesn't expose: cursor and selection
        self.txt._textbox.configure(
            insertbackground=t['fg'], selectbackground=t['select'],
            selectforeground=t['fg'])

    def showContextMenu(self, event):
        try:
            # same font as the menu bar (the default Tk menu font is tiny);
            # menuFont is set once the window is built. Multiply the size
            # here to make this menu larger.
            self.ctxMenu.configure(font=(self.app.menuFont[0], int(self.app.menuFont[1] * 1.0)))
            self.ctxMenu.tk_popup(event.x_root, event.y_root)
        finally:
            self.ctxMenu.grab_release()

    def pollSerial(self):
        """Drain bytes that arrived on the serial port asynchronously
        (e.g. boot/reset messages) and print them in the terminal."""
        try:
            handle = getattr(self.comm, 'handle', None)
            if (handle is not None and handle.is_open
                    and not self.cmdInProgress):
                try:
                    n = handle.in_waiting
                except Exception:      # the port vanished: board off or unplugged
                    n = 0
                    self.app.serCom.connectionLost()
                if n > 0:
                    data = handle.read(n).decode('utf-8', errors='replace')
                    data = data.replace('\r', '')
                    if data:
                        self.txt.insert(END, data)
                        self.txt.mark_set(INSERT, END)
                        self.txt.see(INSERT)
                        self.watchBootMessage(data)
        except Exception as e:
            print(f'pollSerial error: {e}')
        finally:
            self.after(self.pollIntervalMs, self.pollSerial)

    def watchBootMessage(self, data):
        """The board detects its device after power-up or RESET and prints a
        banner. Keep the status bar in step with it: 'Detecting flash part'
        clears the device, 'Part info: <part> ...' sets it."""
        self.bootBuf = (getattr(self, 'bootBuf', '') + data)[-2000:]
        if 'Detecting flash part' in self.bootBuf:
            self.app.serCom.deviceDetected('')
            self.bootBuf = self.bootBuf.split('Detecting flash part')[-1]
        m = re.search(r'Part info:\s*(\S+)\s', self.bootBuf)  # whole word received
        if m:
            self.app.serCom.deviceDetected(m.group(1))
            self.bootBuf = ''

    def displayText(self, text):
        self.txt.insert(END, '\n' + text)
        self.txt.insert(END, '\n' + PROMPT)
        self.txt.mark_set(INSERT, END)
        self.txt.see(INSERT)

    def onReturnKey(self, _event):
        if self.app.serCom.scriptRunning:
            return 'break'          # the script owns the board
        cmdstr = self.txt.get("end-1l linestart", "end-1l lineend")[
            len(PROMPT):].strip()
        if len(cmdstr) > 0:
            self.history.append(cmdstr)

        if cmdstr == CLEAR_CMD:
            self.clear()
            return 'break'
        elif len(cmdstr) > 0:
            resp = self.execute(cmdstr)
            if resp != '':
                self.txt.insert(END, '\n' + resp)

        self.txt.insert(END, '\n' + PROMPT)
        self.txt.mark_set(INSERT, END)
        self.txt.see(INSERT)
        self.historyIndex = len(self.history)
        # Returning 'break' prevents the native behavior, i.e. line break.
        return 'break'

    def execute(self, cmdstr):
        """Sends one command to the board and returns the reply text"""
        self.cmdInProgress = True
        try:
            self.comm.send(cmdstr)
            resp = self.comm.response(removeCmd=True, removePrompt=True).strip()
        except Exception as e:
            resp = f'error from boardcom: {e}'
        finally:
            self.cmdInProgress = False
        return resp

    def runScriptCommand(self, cmdstr):
        """Runs cmdstr as if it had been typed (the command and its reply are
        shown in the Terminal) and returns the reply"""
        self.ensureActiveLine()
        self.txt.delete('end-1l linestart+%dc' % len(PROMPT), 'end-1c')
        self.txt.insert(END, cmdstr)
        if cmdstr == CLEAR_CMD:
            self.clear()
            return ''
        resp = self.execute(cmdstr)
        if resp != '':
            self.txt.insert(END, '\n' + resp)
        self.txt.insert(END, '\n' + PROMPT)
        self.txt.mark_set(INSERT, END)
        self.txt.see(INSERT)
        return resp

    def scriptPrint(self, text):
        """Shows a line printed by a script, above the prompt line"""
        self.ensureActiveLine()
        self.txt.delete('end-1l linestart', 'end-1c')     # drop the empty prompt
        self.txt.insert(END, text + '\n' + PROMPT)
        self.txt.mark_set(INSERT, END)
        self.txt.see(INSERT)

    def ensureActiveLine(self):
        """Moves the cursor to the end of the active prompt line unless it is
        already on that line (after the prompt). Returns True if it moved."""
        line, col = map(int, self.txt.index(INSERT).split('.'))
        lastLine = int(self.txt.index('end-1c').split('.')[0])
        if line == lastLine and col >= len(PROMPT):
            return False
        self.txt.tag_remove('sel', '1.0', END)
        self.txt.mark_set(INSERT, 'end-1c')
        self.txt.see(INSERT)
        return True

    def onKeyPress(self, event):
        """Earlier output is read-only (select/copy only): typing a character
        jumps the cursor to the prompt line first; other edits are blocked."""
        ch = event.char
        if ch and ch.isprintable():
            self.ensureActiveLine()      # then the character is inserted there
            return None
        if ch:                           # a control character
            key = event.keysym.lower()
            if key in ('c', 'a'):        # copy / select all
                return None
            if key == 'v':               # paste goes to the prompt line
                self.ensureActiveLine()
                return None
            return 'break'               # Tab, Ctrl+X/Z/Y, ...
        return None                      # navigation and modifier keys

    def onPaste(self, _event):
        """Pastes onto the prompt line as ONE clean command line: no '>>>', no
        line breaks, no invisible characters (see run_cmd_script.clean_pasted)"""
        try:
            text = self.txt.clipboard_get()
        except Exception:               # empty clipboard or not text
            return 'break'
        self.ensureActiveLine()
        self.txt.insert(INSERT, run_cmd_script.clean_pasted(text))
        self.txt.see(INSERT)
        return 'break'

    def onBackSpace(self, _event):
        if self.ensureActiveLine():
            return 'break'               # just jump to the prompt line
        return self.allowDelete(5)

    def onDelete(self, _event):
        if self.ensureActiveLine():
            return 'break'
        return self.allowDelete(4)

    def allowDelete(self, charIndex):
        cur = self.txt.index(INSERT)
        charPos = int(cur.split('.')[1])
        if charPos < charIndex:
            return 'break'  # Returning 'break' prevents the native behavior, e.g. Del

    def onUpArrowKey(self, _event):
        if self.historyIndex > 0:
            self.historyIndex -= 1
        return self.replaceLineWithHistory()

    def onDownArrowKey(self, _event):
        if self.historyIndex < len(self.history):
            self.historyIndex += 1
        return self.replaceLineWithHistory()

    def onLeftArrowKey(self, _event):
        return self.allowDelete(5)

    def replaceLineWithHistory(self):
        self.txt.delete('end-1l linestart+' +
                        str(len(PROMPT)) + 'c', 'end-1l lineend')

        newLine = ''
        if self.historyIndex < len(self.history):
            newLine = self.history[self.historyIndex]
        self.txt.insert(END, newLine)
        return 'break'  # Returning 'break' prevents the native behavior, e.g. Up/Down/Return

    def clear(self):
        self.txt.delete(1.0, END)
        self.txt.insert(1.0, PROMPT)
        self.txt.mark_set(INSERT, END)

    def tprint(self, text, printOn='guiConsole'):
        """Targeted Print\n
        Prints on the targeted console\n
        Input parameters:\n
        text: the text to be printed
        printOn: the target where to print the messages:
            'sysConsole' prints on system console
            'guiConsole' prints in the GUI text window
            'both' prints in both places (it slows down the system)
        """
        if printOn == 'sysConsole':
            print(text)
        elif printOn == 'guiConsole':
            # term.displayText(text)
            self.displayText(text)
            self.app.du.textToDisplay = ""
        else:
            print(text)
            # term.displayText(text)
            self.displayText(text)
            self.app.du.textToDisplay = ""

    def callCommand(self):
        pass

# class MainWindow:
#     def __init__(self, parent):  # parent or master are good names
#         frame = Frame(parent)    # want to put in into main window (master)
#         frame.pack()

#         self.printButton = Button(frame, text='Print Message', command=self.printMessage)
#         self.printButton.pack(side=LEFT)

#         self.quitButton = Button(frame, text='Quit', command=frame.quit)
#         self.quitButton.pack(side=LEFT)

#     def printMessage(self):
#         print("Wow! It worked :)")


class App:
    """The Dubrovnik Workbench: builds the window, the panels and the menus, and
    holds what they share (the settings panel serCom, the Terminal, the board
    library object). The menu actions and dialogs are its methods."""

    def __init__(self):
        app = self      # for the nested class below, whose own self is another object

        self.root = ctk.CTk()
        self.root.title(f'Dubrovnik Workbench {APP_VERSION}')

        comm = boardcom.BoardComm()   # create an instance of class Comm
        self.du = dubrovnik.Dubrovnik()

        portList = comm.findPorts(exit_if_none=False)   # may be empty: no board yet

        # *******************************************
        # ****** Serial Communications Panel ********
        # *******************************************
        self.settings = Settings()
        self.serCom = SerComFrame(self.root, self, DEBUG=False)
        self.serCom.grid(row=1, column=0, padx=(10, 3), pady=(8, 4), sticky=NSEW)
        if portList:
            self.serCom.combo.set(portList[0])
        self.serCom.comm = comm
        self.serCom.checkLink()      # notices when the board is switched off

        # ******************************
        # ****** Erase Panel   *********
        # ******************************
        # The three panels sit in one row container so that hidden panels collapse
        # and the remaining ones close up (see layoutPanels below).
        self.panelRow = ctk.CTkFrame(self.root, fg_color='transparent', corner_radius=0)
        self.panelRow.grid(row=2, column=0, columnspan=4, sticky=NW)
        self.erase = EraseFrame(self.panelRow, self, DEBUG=False)
        self.erase.comm = comm

        # ******************************
        # ****** Program Panel *********
        # ******************************
        # TODO rename program to progFrm
        self.program = ProgramFrame(self.panelRow, self, DEBUG=False)
        self.program.comm = comm

        # ***************************
        # ****** Read Panel *********
        # ***************************
        self.read = ReadFrame(self.panelRow, self, DEBUG=False)
        self.read.comm = comm

        # ***********************************
        # ******** Terminal Window **********
        # ***********************************
        self.term = Terminal(self.root, self)
        self.term.grid(row=3, column=0, padx=10, pady=4, columnspan=4, sticky=NSEW)
        self.term.grid_columnconfigure(0, weight=1)
        self.term.grid_rowconfigure(1, weight=1)  # txt widget lives at row 1
        self.term.comm = comm     # initializeing self.com in Erase class

        # Let the terminal row absorb all extra vertical space, and let the three
        # panel columns share extra horizontal space evenly.
        self.root.grid_rowconfigure(3, weight=1)
        # Panels keep their natural width; only the spacer column 3 absorbs extra
        # horizontal space, so widening the window doesn't stretch the panels.
        for col in (0, 1, 2):
            self.root.grid_columnconfigure(col, weight=0)
        self.root.grid_columnconfigure(3, weight=1)

        # ***************************
        # ****** Status Bar *********
        # ***************************
        self.stsBarComm = ctk.CTkLabel(self.root, text='Not connected', anchor='w')
        self.stsBarComm.grid(row=5, column=0, padx=10, pady=4,
                        columnspan=4, sticky=EW)

        # stsBarRight = Label(root, text='Hello', width=10, font=(
        #     "Helvetica", 9), anchor=W, justify=RIGHT, pady=2)
        # stsBarRight.config(bd=1, relief=SUNKEN)
        # # stsBarComm.pack(side=BOTTOM, fill=X, anchor=W, padx=10, pady=10)
        # stsBarRight.grid_propagate(0)
        # stsBarRight.grid(row=4, column=1, padx=10, pady=4,sticky='EW')

        # ############ MENU
        # A native Windows menu bar ignores font settings, so build the bar from
        # CTk buttons (row 0) that pop up regular menus, whose font can be set.
        self.scale = ScalingTracker.get_widget_scaling(self.root)
        self.menuFamily = ctk.ThemeManager.theme['CTkFont']['family']
        self.menuFont = (self.menuFamily, -round(MENU_SIZES[self.serCom.menuSize] * self.scale))
        self.menuButtons = []     # (button, font, label) of the menu bar, see applyMenuSize
        self.menuBar = ctk.CTkFrame(self.root, corner_radius=0, height=30)
        self.menuBar.grid(row=0, column=0, columnspan=4, sticky=EW)

        class MenuBarHolder:
            """Stand-in for the menu bar: add_cascade() adds a button to menuBar
            that pops up the given menu just below itself."""
            col = 0

            def add_cascade(self, label, menu):
                def popup():
                    try:
                        menu.tk_popup(btn.winfo_rootx(),
                                      btn.winfo_rooty() + btn.winfo_height())
                    finally:
                        menu.grab_release()
                font = ctk.CTkFont(size=MENU_SIZES[app.serCom.menuSize])
                btn = ctk.CTkButton(
                    app.menuBar, text=label, width=font.measure(label) + 20, height=26,
                    corner_radius=4, fg_color='transparent',
                    hover_color=PAL['hover'], text_color=PAL['text'],
                    font=font, command=popup)
                btn.grid(row=0, column=self.col, padx=(4 if self.col == 0 else 0, 0),
                         pady=2)
                app.menuButtons.append((btn, font, label))
                self.col += 1

        my_menu = MenuBarHolder()

        self.file_menu = Menu(self.root, tearoff=False, font=self.menuFont)
        my_menu.add_cascade(label="File", menu=self.file_menu)
        # File > Firmware: open a firmware file and program it (like Scripts below)
        self.firmware_menu = Menu(self.file_menu, tearoff=False, font=self.menuFont)
        self.file_menu.add_cascade(label="Firmware", menu=self.firmware_menu)
        self.firmware_menu.add_command(label="Open File...", accelerator="Ctrl+O",
                                  command=lambda: self.openForProgramming())
        self.firmware_menu.add_command(label="View File...",
                                  command=lambda: self.showFileViewer())
        self.firmware_menu.add_command(label="Program Loaded File", accelerator="Ctrl+P",
                                  command=lambda: self.programLoadedFile())
        self.firmware_menu.add_command(label="No file loaded", state=DISABLED)
        self.firmware_menu.add_command(label="Close File",
                                  command=lambda: self.closeLoadedFile())
        scripts_menu = Menu(self.file_menu, tearoff=False, font=self.menuFont)
        self.file_menu.add_cascade(label="Scripts", menu=scripts_menu)
        scripts_menu.add_command(label="Run Command Script...",
                                 command=lambda: self.runScript())
        scripts_menu.add_command(label="Run Python Script...",
                                 command=lambda: self.runPythonScript())
        scripts_menu.add_separator()
        scripts_menu.add_command(label="Stop Script  (Esc)",
                                 command=lambda: self.stopScript())
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Save Terminal Log...",
                              command=lambda: self.saveTerminalLog())
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=lambda: self.onClose())

        self.tools_menu = Menu(self.root, tearoff=False, font=self.menuFont,
                          postcommand=lambda: self.refreshTools())
        my_menu.add_cascade(label="Tools", menu=self.tools_menu)

        # View menu: panel visibility, window appearance and Terminal colours.
        # (Radio items mark the current choice.)
        self.view_menu = Menu(self.root, tearoff=False, font=self.menuFont)
        my_menu.add_cascade(label="View", menu=self.view_menu)
        self.view_menu.add_command(label='Hide Panels (Erase/Program/Read)',
                              command=lambda: self.onPanelToggle())

        # File > Parameters: save / load / reset the entry-box values of the Erase,
        # Program and Read panels (the only settings that are NOT saved automatically)
        params_menu = Menu(self.file_menu, tearoff=False, font=self.menuFont)
        self.file_menu.insert_cascade(5, label="Parameters", menu=params_menu)
        self.file_menu.insert_separator(6)                    # before "Exit"

        # Scripts (File > Scripts). Both kinds run on the GUI thread and call
        # root.update() between commands, so the window stays alive and Esc is seen.
        #   Command script: a text file, one Terminal command per line
        #                   (see dubLibs/run_cmd_script.py)
        #   Python script : a Python file that uses the `dub` object
        #                   (see dubLibs/run_py_script.py)
        self.scriptStop = [False]

        self.root.bind('<Escape>', lambda _e: self.stopScript())

        self.firmware_menu.configure(postcommand=self.refreshFileMenu)

        self.root.bind('<Control-o>', self.fileShortcut(lambda: self.openForProgramming()))
        self.root.bind('<Control-p>', self.fileShortcut(lambda: self.programLoadedFile()))
        self.term.txt.bind('<Control-o>', self.fileShortcut(lambda: self.openForProgramming()))
        self.term.txt.bind('<Control-p>', self.fileShortcut(lambda: self.programLoadedFile()))

        params_menu.add_command(label="Save", command=self.saveParams)
        params_menu.add_command(label="Load", command=self.loadParams)
        params_menu.add_command(label="Defaults", command=self.defaultParams)

        # Window appearance and Terminal colours (part of the View menu)
        self.appearanceVar = StringVar(value=self.serCom.appearance)
        appearance_menu = Menu(self.view_menu, tearoff=False, font=self.menuFont)
        self.view_menu.add_separator()
        self.view_menu.add_cascade(label="Appearance", menu=appearance_menu)
        self.view_menu.add_command(label="Terminal...",
                              command=lambda: self.showTerminalDialog())
        self.view_menu.add_command(label="Hex Dump...",
                              command=lambda: self.showHexDialog())
        menuSizeMenu = Menu(self.view_menu, tearoff=False, font=self.menuFont)
        self.view_menu.add_cascade(label="Menu text size", menu=menuSizeMenu)
        self.menuSizeVar = StringVar(value=self.serCom.menuSize)

        for label, value in (('Small', 'small'), ('Normal', 'normal'),
                             ('Large', 'large')):
            menuSizeMenu.add_radiobutton(label=label, value=value,
                                         variable=self.menuSizeVar, command=self.setMenuSize)

        for label, value in (('Light', 'light'), ('Dark', 'dark'),
                             ('System (follow Windows)', 'system')):
            appearance_menu.add_radiobutton(label=label, value=value,
                                            variable=self.appearanceVar,
                                            command=self.setAppearance)

        self.zoomState = dict(save=None, restore=None, old=None)

        self.term.onZoom = self.zoomTerminal

        self.fileViewer = None

        self.hexDialog = None

        self.fontCache = []

        self.termDialog = None

        help_menu = Menu(self.root, tearoff=False, font=self.menuFont)
        my_menu.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Help", accelerator="F1", command=showHelp)
        self.root.bind('<F1>', showHelp)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self.showAbout)

        # Help > Documents: one entry for every file in the docs folder
        # (see dubLibs/documents.py); rebuilt each time the submenu opens.
        self.docs_menu = Menu(help_menu, tearoff=False, font=self.menuFont,
                         postcommand=lambda: self.refreshDocs())
        help_menu.insert_cascade(1, label="Documents", menu=self.docs_menu)
        help_menu.insert_command(2, label="Datasheet", command=lambda: self.openDatasheet())
        help_menu.insert_command(3, label="Datasheet Source...",
                                 command=lambda: self.editDatasheetUrl())

        # Help > Assistant: chat window backed by dubLibs/assistant.py. It answers
        # from the help and proposes scripts; nothing runs without the user's OK.
        self.assistant = None             # dubLibs.assistant.Assistant, made when first needed
        self.assistantWindow = None

        from dubLibs import assistant as assistantLib
        if assistantLib.configured():       # hidden unless a model is set up
            help_menu.insert_command(4, label="Assistant...", command=self.showAssistant)

        self.serCom.loadConfig()  # includes autoConnect and lastUsedPort
        self.allMenus = (self.file_menu, self.firmware_menu, self.tools_menu, self.view_menu, params_menu, scripts_menu,
                    help_menu, self.docs_menu, appearance_menu, menuSizeMenu)
        self.menuSizeVar.set(self.serCom.menuSize)
        self.applyMenuSize()          # the size just loaded from the settings file
        self.syncTheme()
        self.watchSystemAppearance()
        self.syncPanels()

        # Save the connection settings whenever they change, so they survive even
        # if the app is killed instead of closed normally. The entry-box values are
        # saved only by File > Parameters > Save.
        # (Traces are added after loadConfig so loading doesn't trigger a save.)
        self.serCom.chk_var.trace_add('write', lambda *_args: self.serCom.saveConfig())

        # * At this point we have a list of valid COM ports.
        # * Next step is to connect to one of them.
        if self.serCom.autoConnect and portList:  # auto connect, if a board was found
            if len(portList) > 1:  # no need to check if ==0. boardcom.py already does
                if self.serCom.lastUsedPort in portList:  # if last used port is in the portList
                    # connect to that port
                    self.serCom.connectPort(self.serCom.lastUsedPort,
                                       checkIsFlashPresent=False)
            else:
                # otherwise connect to the first in the list
                self.serCom.connectPort(portList[0], checkIsFlashPresent=False)
        # If not autoconnect then do not connect to anything

            # * At this point we are connected to the UART chip on Dubrovnik, but not yet
            # * to the MCU. It may require a manual RESET to boot.
            if self.serCom.portStatus == 'connected':   # the port could be opened
                resp = comm.connectToMCU()
                # print(resp)
                self.term.clear()

                if comm.isFlashPresent() == 0:
                    showwarning(
                        'Warning', 'No flash device detected\nInstall a device and RESET the board')
                else:                   # show the device in the status bar
                    try:
                        self.serCom.deviceDetected(self.du.get_part_number(comm))
                    except Exception:
                        pass            # the status bar just shows no device

        elif self.serCom.autoConnect:     # Auto connect is on, but no board was found
            showwarning(
                'No board found',
                'No Dubrovnik board was found.\n\n1. Connect the USB cable\n'
                '2. Turn on the board\n3. Press the RESET button\n\n'
                'Then click Connect (the COM port list refreshes when you open it).')

        # Board commands (volt, freq, config, ...) don't need a flash device, so the
        # terminal must stay usable. The modal warning steals focus: give it back.
        self.root.focus_force()
        self.term.txt.focus_set()
        self.term.txt.mark_set(INSERT, END)

        self.stsBarComm.configure(text=self.serCom.serParams)

        # The minimum width is the natural width of the visible panels (with their
        # margins), so those stay fully visible; the window can be freely enlarged
        # or shrunk down to that. Capped to the screen so it still fits on small
        # monitors. CTk's minsize()/geometry() take unscaled units, while
        # winfo_req*() return physical pixels, hence the division by `scale`.
        self.root.update_idletasks()
        self.scale = self.root._get_window_scaling()
        # widget scaling = window scaling unless a UI scale (e.g. compact) is set
        self.wscale = ScalingTracker.get_widget_scaling(self.root)
        # Tk's winfo_screenwidth/height() are already divided by the DPI scaling
        # here (e.g. 3413x1440 on a 5120x2160 screen); ask Windows for real pixels.
        try:
            import ctypes
            metrics = ctypes.windll.user32.GetSystemMetrics
            self.scrW, self.scrH = metrics(0), metrics(1)                  # primary screen
            # all monitors together (the origin can be negative)
            vx, vy, vw, vh = metrics(76), metrics(77), metrics(78), metrics(79)
        except Exception:
            self.scrW, self.scrH = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            vx, vy, vw, vh = 0, 0, self.scrW, self.scrH
        self.marginW, self.marginH = 40, 80  # leave room for taskbar / window chrome
        self.MIN_WIN_W = 420            # never narrower than this (unscaled px)

        minW, startH, minH = self.computeLimits()
        self.root.minsize(width=minW, height=minH)
        # Restore the window size saved at the last exit, if it fits on this
        # display; otherwise (or on first run) use the default size.
        winW, winH = minW, startH
        if self.serCom.winSize:
            savedW, savedH = self.serCom.winSize
            if (savedW <= (self.scrW - self.marginW) / self.scale
                    and savedH <= (self.scrH - self.marginH) / self.scale):
                winW, winH = max(int(savedW), minW), max(int(savedH), minH)
        geom = f'{winW}x{winH}'
        if self.serCom.winPos:
            # restore the position only if the window's title bar would still be
            # reachable on one of the monitors (a monitor may have been removed)
            x, y = self.serCom.winPos
            if (vx - 100 < x < vx + vw - 100 and vy - 10 <= y < vy + vh - 60):
                geom += f'+{x}+{y}'
        self.root.geometry(geom)

        self.root.protocol('WM_DELETE_WINDOW', self.onClose)

    def run(self):
        """Shows the window and handles events until it is closed"""
        self.root.mainloop()


    # def updtStsBar(statusMsg):
    #     print(statusMsg)
    #     stsBarComm.config(text=statusMsg)

    def layoutPanels(self):
        """Shows or hides the three panels together (serCom.showPanels). Shown
        panels sit side by side from the left, with 10 px outer margins and
        3 px between neighbours."""
        if not self.serCom.showPanels:
            self.panelRow.grid_remove()
            self.root.grid_columnconfigure(0, minsize=0)
            return
        for col, (frame, padx) in enumerate(
                ((self.erase, (10, 3)), (self.program, 3), (self.read, (3, 10)))):
            frame.grid(row=0, column=col, pady=4, padx=padx, sticky=NSEW)
        self.panelRow.grid(row=2, column=0, columnspan=4, sticky=NW)
        # Make the Serial Connection panel (column 0 of the window) as wide as
        # the Erase panel below it: Erase's width plus its 10 px + 3 px margins
        self.root.update_idletasks()
        margins = 13 * ScalingTracker.get_widget_scaling(self.root)
        self.root.grid_columnconfigure(0, minsize=round(self.erase.winfo_reqwidth() + margins))

    def panelsLabel(self):
        """Text of the first View item: the action it will do"""
        return ('Hide Panels (Erase/Program/Read)' if self.serCom.showPanels
                else 'Show Panels (Erase/Program/Read)')

    def syncPanels(self):
        """Applies serCom.showPanels to the menu text and the layout"""
        self.view_menu.entryconfigure(0, label=self.panelsLabel())
        self.layoutPanels()

    def onPanelToggle(self):
        """The first View item was clicked: show or hide the panels, then
        change the window height by the height gained or lost so the Terminal
        keeps its size"""
        self.serCom.showPanels = not self.serCom.showPanels
        self.view_menu.entryconfigure(0, label=self.panelsLabel())
        self.root.update_idletasks()
        before = self.root.winfo_reqheight()
        self.layoutPanels()
        self.root.update_idletasks()
        minW, _, minH = self.computeLimits()
        self.root.minsize(width=minW, height=minH)
        delta = (self.root.winfo_reqheight() - before) / self.scale
        h = round(self.root.winfo_height() / self.scale + delta)
        h = max(minH, min(h, int((self.scrH - self.marginH) / self.scale)))
        w = max(minW, round(self.root.winfo_width() / self.scale))
        self.root.geometry(f'{w}x{h}')
        self.serCom.saveConfig()

    def showAbout(self):
        messages.showAbout(self.root)

    def dialogBox(self, title, text, buttons, entryDefault=None):
        """Modal dialog in the Workbench look: see dubGui/dialogs/messages.py"""
        return messages.dialogBox(self.root, title, text, buttons, entryDefault)

    def showStatus(self, msg, ms=3000):
        """Shows msg in the status bar for a few seconds"""
        old = self.stsBarComm.cget('text')
        self.stsBarComm.configure(text=msg)
        self.root.after(ms, lambda: self.stsBarComm.configure(text=old)
                   if self.stsBarComm.cget('text') == msg else None)

    def saveParams(self):
        self.serCom.saveConfig(params=True)
        self.showStatus('Parameters saved')

    def loadParams(self):
        self.serCom.loadConfig(prefs=False)
        self.showStatus('Parameters loaded')

    def defaultParams(self):
        self.serCom.loadDefaultParams()
        self.showStatus('Default parameters restored (File > Parameters > Save '
                   'to keep them)')

    def pickScript(self, title, filetypes):
        """Asks for a script file and remembers its folder; returns the path"""
        name = askopenfilename(
            title=title, initialdir=self.serCom.scriptDir or defaultScriptDir(),
            filetypes=filetypes)
        if name:
            self.serCom.scriptDir = os.path.dirname(name)      # start here next time
            self.serCom.saveConfig()
        return name

    def scriptReady(self):
        """True if a script may be started now"""
        if self.serCom.scriptRunning:
            return False
        if self.serCom.portStatus != 'connected':
            self.serCom.checkConnection()
            return False
        return True

    def runScript(self):
        """File > Scripts > Run Command Script"""
        if not self.scriptReady():
            return
        name = self.pickScript('Run Command Script', (
            ('Script files', '*.txt *.scr'), ('All files', '*.*')))
        if not name:
            return
        try:
            with open(name, encoding='utf-8-sig') as fh:
                commands = run_cmd_script.parse(fh.read())
        except (OSError, UnicodeDecodeError) as e:
            showerror('Run Command Script', f'Could not read the file:\n{e}')
            return
        if not commands:
            showinfo('Run Command Script', 'The file contains no commands.')
            return
        self.serCom.scriptRunning = True
        self.scriptStop[0] = False
        self.term.scriptPrint(f'--- Running script {os.path.basename(name)} '
                         f'({len(commands)} commands) ---')
        reason = None
        try:
            for lineno, cmd in commands:
                if self.scriptStop[0]:
                    reason = 'stopped by the user'
                    break
                reply = self.term.runScriptCommand(cmd)
                self.root.update()
                if run_cmd_script.is_error(reply):
                    reason = f'error at line {lineno}: {cmd}'
                    break
        finally:
            self.serCom.scriptRunning = False
        self.term.scriptPrint('--- Script finished ---' if reason is None
                         else f'--- Script stopped: {reason} ---')

    def runPythonScript(self):
        """File > Scripts > Run Python Script"""
        if not self.scriptReady():
            return
        name = self.pickScript('Run Python Script', (
            ('Python scripts', '*.py'), ('All files', '*.*')))
        if not name:
            return
        self.executePython(name)

    def executePython(self, path):
        """Runs a Python file with the `dub` object and reports how it ended"""
        api = run_py_script.DubApi(
            self.term, self.du, self.root.update, lambda: self.scriptStop[0],
            ask=lambda prompt, default='': self.dialogBox(
                'Script', prompt, [('OK', None), ('Cancel', None)], default),
            confirm=lambda question: self.dialogBox(
                'Script', question, [('Yes', True), ('No', False)]),
            notify=lambda text: self.dialogBox('Script', text, [('OK', None)]),
            hex_options=lambda: dict(
                per_row=self.serCom.hexRow, show_ascii=self.serCom.hexAscii,
                upper=self.serCom.hexUpper, gap=self.serCom.hexGap))
        self.serCom.scriptRunning = True
        self.scriptStop[0] = False
        self.term.scriptPrint(f'--- Running Python script {os.path.basename(path)} ---')
        try:
            ok, message = run_py_script.run_file(path, api, self.term)
        finally:
            self.serCom.scriptRunning = False
        self.term.scriptPrint('--- Script finished ---' if ok
                         else f'--- Script stopped: {message} ---')

    def stopScript(self):
        self.scriptStop[0] = True

    # Tools menu: one entry for every script in the tools folder that has a
    # "# TOOL: name" header (see dubLibs/tools.py). Rebuilt each time it opens.
    def runTool(self, tool):
        if not self.scriptReady():
            return
        if tool['confirm'] and not self.dialogBox(
                tool['name'], tool['confirm'], [('Yes', True), ('No', False)]):
            return
        if tool['description']:
            self.showStatus(tool['description'], 8000)
        self.executePython(tool['path'])

    def openToolsFolder(self):
        folder = toolsFolder()
        if os.path.isdir(folder):
            os.startfile(folder)
        else:
            showerror('Tools', f'The tools folder was not found:\n{folder}')

    def refreshTools(self):
        self.tools_menu.delete(0, 'end')
        found = tools.find_tools(toolsFolder())
        for tool in found:
            self.tools_menu.add_command(label=tool['name'],
                                   command=lambda t=tool: self.runTool(t))
        if not found:
            self.tools_menu.add_command(label='(no tools found)', state='disabled')
        self.tools_menu.add_separator()
        self.tools_menu.add_command(label='Open Tools Folder',
                               command=self.openToolsFolder)

    def openForProgramming(self):
        """File > Firmware > Open File: pick a .bin, S-record or Intel HEX file and
        set the Program panel up for it ("Load from File" mode)"""
        if self.program.openFile():
            self.program.progModeVar.set('file')
            self.program.grayOutEntry()

    def programLoadedFile(self):
        """File > Firmware > Program Loaded File: with the panels shown it asks for a
        confirmation (the Offset is the one in the Program panel); with the
        panels hidden the question also asks for the Offset."""
        image = self.program.image
        if image is None:
            showinfo('Program', 'No file is loaded.\nUse File > Open Firmware '
                     'File first.')
            return
        if not self.scriptReady():
            return
        if self.serCom.showPanels:
            try:
                offset = parseField('Offset', self.program.start_addr.get())
            except ValueError as e:
                showerror('Program', str(e))
                return
            text = (f'Program {self.program.imageName} ({image.describe()})?\n\n'
                    f'It will be written to:\n{self.program.rangesText(offset)}\n\n'
                    'Nothing is erased first.')
            if not self.dialogBox('Program File', text,
                             [('Program', True), ('Cancel', False)]):
                return
        else:
            text = (f'Program {self.program.imageName} ({image.describe()}).\n\n'
                    f'Addresses in the file:\n{self.program.rangesText()}\n\n'
                    'Offset (hex) added to every address, normally 0. '
                    'Nothing is erased first.')
            answer = self.dialogBox('Program File', text,
                               [('Program', None), ('Cancel', False)], '0')
            if answer is False:
                return
            try:
                offset = parseField('Offset', answer)
            except ValueError as e:
                showerror('Program', str(e))
                return
            self.program.start_addr.set(f'{offset:X}')
        self.program.progModeVar.set('file')
        self.program.grayOutEntry()
        self.program.program()

    def closeLoadedFile(self):
        """File > Firmware > Close File: forget the loaded file"""
        self.program.closeFile()
        self.showStatus('File closed')

    def refreshFileMenu(self):
        """Firmware menu opens: Program and Close need a loaded file; the grey
        line says which one is loaded"""
        image = self.program.image
        state = NORMAL if image is not None else DISABLED
        for index in (1, 2, 4):        # View File, Program, Close File
            self.firmware_menu.entryconfigure(index, state=state)
        self.firmware_menu.entryconfigure(
            3, label=(f'Loaded: {self.program.imageName} ({image.size} bytes)'
                      if image is not None else 'No file loaded'))

    def fileShortcut(self, action):
        """Runs a menu action from a key; 'break' keeps the Terminal's own
        Ctrl+O / Ctrl+P (open line, previous line) from also running"""
        def handler(_event=None):
            action()
            return 'break'
        return handler

    def saveTerminalLog(self):
        """File > Save Terminal Log: write the Terminal contents to a text file"""
        name = asksaveasfilename(
            title='Save Terminal Log', defaultextension='.txt',
            initialfile=datetime.datetime.now().strftime(
                'dubrovnik_terminal_%Y%m%d_%H%M%S.txt'),
            filetypes=(('Text files', '*.txt'), ('All files', '*.*')))
        if not name:
            return
        try:
            with open(name, 'w', encoding='utf-8') as fh:
                fh.write(self.term.txt.get('1.0', 'end-1c') + '\n')
        except OSError as e:
            showerror('Save Terminal Log', f'Could not write the file:\n{e}')
            return
        self.showStatus('Terminal log saved')

    def applyMenuSize(self):
        """Applies serCom.menuSize to the menu bar and all pop-up menus"""
        size = MENU_SIZES[self.serCom.menuSize]
        self.menuFont = (self.menuFamily, -round(size * self.scale))
        for btn, font, label in self.menuButtons:
            font.configure(size=size)
            btn.configure(width=font.measure(label) + 20)
        for m in self.allMenus:
            m.configure(font=self.menuFont)

    def setMenuSize(self):
        self.serCom.menuSize = self.menuSizeVar.get()
        self.applyMenuSize()
        self.serCom.saveConfig()

    def applyAppearance(self):
        ctk.set_appearance_mode(self.serCom.appearance)
        styleCombobox(self.root)
        styleMenus(self.allMenus)
        self.applyTerminal()            # the 'auto' Terminal theme follows the window

    def watchSystemAppearance(self, lastMode=[None]):
        """In 'System' mode Windows can switch light/dark while the app runs;
        re-apply the appearance rules when that happens."""
        mode = ctk.get_appearance_mode()
        if lastMode[0] not in (None, mode) and self.serCom.appearance == 'system':
            self.applyAppearance()
            self.serCom.saveConfig()
        lastMode[0] = mode
        self.root.after(2000, self.watchSystemAppearance)

    def setAppearance(self):
        self.serCom.appearance = self.appearanceVar.get()
        self.applyAppearance()
        self.serCom.saveConfig()

    def syncTheme(self):
        """Applies serCom.appearance and the Terminal look (e.g. just loaded
        from the settings file)"""
        self.appearanceVar.set(self.serCom.appearance)
        self.applyAppearance()

    # ---- Terminal look: View > Terminal... and Ctrl + mouse wheel ----------
    def termColors(self):
        """The Terminal colours (bg, fg, select) of the chosen theme"""
        theme = self.serCom.termTheme
        if theme == 'auto':
            theme = 'dark' if ctk.get_appearance_mode() == 'Dark' else 'light'
        if theme == 'custom':
            return dict(bg=self.serCom.termBg, fg=self.serCom.termFg,
                        select=self.serCom.termSelect)
        return TERM_THEMES[theme]

    def applyTerminal(self):
        self.term.applyColors(self.termColors())
        self.term.setFont(self.serCom.termFont, self.serCom.termFontSize)

    def zoomTerminal(self, step):
        """Ctrl + mouse wheel: bigger or smaller Terminal text. The setting is
        saved shortly after the wheel stops."""
        size = min(max(self.serCom.termFontSize + step, TERM_SIZE_MIN), TERM_SIZE_MAX)
        if size != self.serCom.termFontSize:
            self.serCom.termFontSize = size
            self.applyTerminal()
            if self.zoomState['save']:
                self.root.after_cancel(self.zoomState['save'])
            self.zoomState['save'] = self.root.after(600, self.serCom.saveConfig)
        # show the size in the status bar, then put the old text back
        if self.zoomState['restore']:
            self.root.after_cancel(self.zoomState['restore'])
        else:
            self.zoomState['old'] = self.stsBarComm.cget('text')
        self.stsBarComm.configure(text=f'Terminal text size {size}')

        def restore():
            self.stsBarComm.configure(text=self.zoomState['old'])
            self.zoomState['restore'] = None
        self.zoomState['restore'] = self.root.after(1500, restore)

    def showFileViewer(self):
        """File > Firmware > View File: the whole loaded file as a hex dump, at
        the addresses it will be written to (file address + Offset)"""
        image = self.program.image
        if image is None:
            showinfo('View File', 'No file is loaded.\nUse File > Firmware > '
                     'Open File first.')
            return
        try:
            offset = parseField('Offset', self.program.start_addr.get())
        except ValueError:
            offset = 0
        old = self.fileViewer
        if old is not None and old.win.winfo_exists():
            old.win.destroy()
        self.fileViewer = FileViewer(
            self.root, image, self.program.imageName, offset, self.termColors(),
            self.serCom.termFont, self.serCom.termFontSize,
            hexOptions(self.serCom))

    def showHexDialog(self):
        """View > Hex Dump...: layout of the Hex Dump display mode of the Read
        panel, with a sample. Nothing changes until OK."""
        if self.hexDialog is not None and self.hexDialog.win.winfo_exists():
            self.hexDialog.win.focus_set()
            return
        self.hexDialog = HexDialog(self.root, self.serCom, self.termColors,
                                   CFG_DEFAULTS)

    def monospacedFonts(self):
        """Installed fixed-width fonts (found once; see termstyle)"""
        if not self.fontCache:
            self.fontCache.extend(termstyle.monospaced_fonts(self.root))
        return list(self.fontCache)

    def showTerminalDialog(self):
        """View > Terminal...: theme, colours, font and size with a preview.
        Changes show in the Terminal at once; Cancel puts the old look back."""
        if self.termDialog is not None and self.termDialog.win.winfo_exists():
            self.termDialog.win.focus_set()
            return
        self.termDialog = TerminalDialog(
            self.root, self.serCom, self.termColors, self.applyTerminal,
            self.monospacedFonts(), CFG_DEFAULTS)

    def assistantFolder(self):
        folder = os.path.join(run_py_script.documents_dir(), 'Dubrovnik',
                              'Assistant')
        os.makedirs(folder, exist_ok=True)
        return folder

    def reviewScript(self, proposal, ai):
        """Shows a proposed script; Run saves it and starts it, Save only
        saves it. The outcome is reported back to the assistant."""
        ScriptReview(self.root, proposal, ai, self.assistantFolder,
                     self.scriptReady, self.executePython, self.showStatus)

    def showAssistant(self):
        win = self.assistantWindow
        if win is not None and win.win.winfo_exists():
            win.win.deiconify()
            win.win.focus_set()
            return
        from dubLibs import assistant
        if self.assistant is None:
            self.assistant = assistant.Assistant(helpFilePath(), toolsFolder())
        problem = self.assistant.available()
        if problem:
            showerror('Assistant', problem)
            return
        self.assistantWindow = AssistantWindow(self.root, self.assistant,
                                               self.reviewScript)

    def openDocument(self, path):
        try:
            os.startfile(path)
        except OSError as e:
            showerror('Documents', f'Could not open the file:\n{path}\n\n{e}')

    def openDatasheet(self):
        """Help > Datasheet: the datasheet of the device in the status bar"""
        part = (datasheet.part_from_status(self.serCom.serParams)
                if self.serCom.portStatus == 'connected' else '')
        if not part:
            showinfo('Datasheet', 'No device is shown in the status bar.\n\n'
                     'Connect the board with a device in the socket first.')
            return
        # the docs folder, then %APPDATA%\Dubrovnik\Datasheets (also searched
        # in a "datasheets" subfolder of docs); no admin rights needed there
        local = datasheet.find_local(
            (docsFolder(), self.serCom.dubrovnikConfigPath), part)
        if local:
            self.openDocument(local)
            self.showStatus(f'Datasheet for {part}: {os.path.basename(local)}', 6000)
            return
        url = datasheet.build_url(self.serCom.datasheetUrl, part)
        try:
            webbrowser.open(url)
        except Exception as e:
            showerror('Datasheet', f'Could not open the browser:\n{url}\n\n{e}')
            return
        self.showStatus(f'Datasheet for {part}: opened {url}', 8000)

    def editDatasheetUrl(self):
        """Help > Datasheet Source...: where to look when there is no local file"""
        text = self.dialogBox(
            'Datasheet Source',
            'Web address used by Help > Datasheet when no datasheet file is in '
            'the docs folder. {part} is replaced by the part number of the '
            'device. An address without {part} is opened as it is.\n\n'
            'Clear the box to go back to the default (Renesas search).',
            [('OK', None), ('Cancel', False)], self.serCom.datasheetUrl)
        if text is False:           # Cancel
            return
        text = (text or '').strip()
        url = datasheet.clean_url(text) if text else datasheet.DEFAULT_URL
        if text and url != text:
            showerror('Datasheet Source', 'The address must start with http:// '
                      'or https://')
            return
        self.serCom.datasheetUrl = url
        self.serCom.saveConfig()
        self.showStatus('Datasheet source saved', 4000)

    def openDocsFolder(self):
        folder = docsFolder()
        if os.path.isdir(folder):
            os.startfile(folder)
        else:
            showerror('Documents', f'The documents folder was not found:\n{folder}')

    def refreshDocs(self):
        self.docs_menu.delete(0, 'end')
        found = documents.find_documents(docsFolder())
        for label, path in found:
            self.docs_menu.add_command(label=label,
                                  command=lambda p=path: self.openDocument(p))
        if not found:
            self.docs_menu.add_command(label='(no documents found)', state='disabled')
        self.docs_menu.add_separator()
        self.docs_menu.add_command(label='Open Documents Folder',
                              command=self.openDocsFolder)

    def computeLimits(self):
        """Returns (min width, natural height, min height) in unscaled px for
        the current set of visible panels"""
        self.root.update_idletasks()
        panelsW = self.root.winfo_reqwidth()   # the panels row sets this
        reqH = self.root.winfo_reqheight()
        minW = min(max(int(panelsW / self.scale), self.MIN_WIN_W),
                   int((self.scrW - self.marginW) / self.scale))
        startH = min(int(reqH / self.scale), int((self.scrH - self.marginH) / self.scale))
        # Height can shrink only until the Terminal text area is
        # TERM_MIN_LINES high
        termStartH, termLineH = 300 * self.wscale / self.scale, 22 * self.wscale / self.scale
        minH = int(min(startH,
                       startH - termStartH + TERM_MIN_LINES * termLineH))
        return minW, startH, minH

    # print(comm.serialAvailable(comport))

    # def timer():
    #     # seconds = time.strftime("%S")
    #     # print(seconds)
    #     # term.displayText(seconds)

    #     numBytes = comm.serialAvailable()
    #     if numBytes > 0:
    #         resp = comm.response()
    #         term.displayText(resp)

    #     # numBytes = comm.serialAvailable(comport)
    #     # term.displayText(str(numBytes))  # print response into the teminal window
    #     # print(f'numBytes: {numBytes}')
    #     timer_lbl.after(1000, timer)  # regularly call function to implement a timer

    # timer_lbl = Label(root, text='')
    # # timer_lbl.pack() # make it invisible. Used as timer for checking serial port
    # timer()  # must call the function once to start it

    def onClose(self):
        """Store the last used entry values and window size on exit."""
        if self.serCom.scriptRunning:          # stop a running script first
            self.stopScript()
            self.root.after(300, self.onClose)
            return
        try:
            if self.root.state() == 'normal':      # not minimized / maximized
                self.serCom.winSize = (round(self.root.winfo_width() / self.scale),
                                  round(self.root.winfo_height() / self.scale))
                self.serCom.winPos = (self.root.winfo_x(), self.root.winfo_y())
            self.serCom.saveConfig()
        finally:
            self.root.destroy()


def main():
    App().run()


if __name__ == "__main__":
    main()
