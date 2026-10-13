# from dubGui.serialTerminalShell import Terminal
import datetime
import time
import os
import pathlib
import re
import sys
import tempfile
import webbrowser
from tkinter import (
    LabelFrame, IntVar, StringVar, Checkbutton, Button, Label,
    Radiobutton, Entry, Menu,
    CHAR, DISABLED, E, END, EW, GROOVE, INSERT, LEFT, NORMAL, NSEW, NW, S,
    SUNKEN, Tk, W, mainloop)
from tkinter import ttk
from tkinter import scrolledtext
import tkinter as tk
from tkinter.colorchooser import askcolor
# Use the dubLibs next to this project, not another copy found on PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dubLibs import boardcom
from dubLibs import cfgfile
from dubLibs import run_cmd_script
from dubLibs import run_py_script
from dubLibs import tools
from dubLibs import datasheet
from dubLibs import documents
from dubLibs import firmware_image
from dubLibs import termstyle
from dubLibs.version import VERSION as APP_VERSION
from dubLibs import dubrovnik  # instead of "from dubLibs import Dubrovnik as du"
from tkinter.filedialog import askopenfilename, asksaveasfilename
from tkinter.messagebox import showerror, showwarning, showinfo, askyesno
from tkinter import simpledialog
# import sys
# import time

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
PANEL_BORDER = 2

# Default value of every remembered setting (also the fallback for bad values)
CFG_DEFAULTS = dict(
    autoConnect=0, lastUsedPort='',
    eraseBlkSize='4', eraseStartAddr='0', eraseNumBlocks='1',
    progPattern='cafe0000', progIncrement='1', progStartAddr='0',
    progLength='100',
    readSpiMode='SPI', readStartAddr='0', readLength='100',
    terminalTheme='light', showPanels=True,
    displayMode='Binary (b)', scriptFolder='', programFolder='',
    # Terminal look (View > Terminal...), as in the Workbench. terminalTheme is
    # one of TERM_CHOICES; the three colours are used by the 'custom' theme.
    terminalBg='#FFFFFF', terminalFg='#000000', terminalSelect='#B5D5FF',
    terminalFont='Consolas', terminalFontSize=11,
    datasheetUrl=datasheet.DEFAULT_URL)     # Help > Datasheet Source...

TERM_CHOICES = ('light', 'dark', 'custom')
TERM_SIZE_MIN, TERM_SIZE_MAX = termstyle.SIZE_MIN, termstyle.SIZE_MAX
HEX_COLOR = termstyle.HEX_COLOR

# Terminal colour themes: background, text and selection colours
TERM_THEMES = {
    'dark': dict(bg='#1B1F24', fg='#D6DBE1', select='#34506E'),
    'light': dict(bg='#FFFFFF', fg='#000000', select='#B5D5FF'),
}


def parseField(name, text, base=16, signed=False):
    """Validates an entry-box string and returns it as an int.
    Raises ValueError with a user-readable message if it is empty or invalid."""
    text = text.strip()
    if text == '':
        raise ValueError(f'"{name}" is empty. Enter a value.')
    try:
        value = int(text, base)
    except ValueError:
        kind = 'hexadecimal' if base == 16 else 'decimal'
        raise ValueError(f'"{name}" is not a valid {kind} number: {text}')
    if value < 0 and not signed:
        raise ValueError(f'"{name}" must not be negative: {text}')
    return value


class ProgramCancelled(Exception):
    """Raised by the progress dialog when the user clicks Cancel"""


class ProgressDialog:
    """Modal progress window: show(text, done) is called from a timer while the
    job runs in a thread. cancelled becomes True when Cancel / Esc is used."""

    def __init__(self, title, total):
        self.total, self.cancelled = max(total, 1), False
        self.start = time.time()
        self.win = tk.Toplevel(root)
        self.win.title(title)
        self.win.resizable(False, False)
        self.win.transient(root)
        self.label = ttk.Label(self.win, text='Starting...', width=56)
        self.label.grid(row=0, column=0, padx=20, pady=(18, 6), sticky='w')
        self.bar = ttk.Progressbar(self.win, length=400, maximum=100)
        self.bar.grid(row=1, column=0, padx=20, pady=6)
        self.info = ttk.Label(self.win, text='', width=56)
        self.info.grid(row=2, column=0, padx=20, pady=(0, 6), sticky='w')
        ttk.Button(self.win, text='Cancel', command=self.cancel
                   ).grid(row=3, column=0, padx=20, pady=(6, 16), sticky='e')
        self.win.protocol('WM_DELETE_WINDOW', self.cancel)
        self.win.bind('<Escape>', lambda _e: self.cancel())
        self.win.update_idletasks()
        x = root.winfo_x() + (root.winfo_width() - self.win.winfo_width()) // 2
        y = root.winfo_y() + (root.winfo_height() - self.win.winfo_height()) // 2
        self.win.geometry(f'+{max(x, 0)}+{max(y, 0)}')
        self.win.update()
        self.win.grab_set()

    def cancel(self):
        self.cancelled = True
        self.label.configure(text='Cancelling...')

    def show(self, text, done):
        pct = min(done / self.total, 1.0)
        if self.cancelled:
            text = 'Cancelling...'
        self.label.configure(text=text)
        self.bar['value'] = pct * 100
        self.info.configure(
            text=f'{pct * 100:.0f} %    {time.time() - self.start:.0f} s elapsed')

    def close(self):
        try:
            self.win.grab_release()
            self.win.destroy()
        except Exception:
            pass


class SerComFrame(LabelFrame):
    def __init__(self, parent=None, DEBUG=False):
        LabelFrame.__init__(self, parent, text='Serial Connection',
                            padx=10, pady=10)
        self.DEBUG = DEBUG
        self.STANDALONE = False
        self.comm = None                      # object created by boardcom
        self.portStatus = 'disconnected'
        self.selPort = ''  # ! keeps track of the selected port, between calls
        self.portList = []
        self.portHandle = None
        self.chk_var = IntVar()
        self.autoConnect = 0
        self.serParams = ''
        self.winSize = None   # (width, height) of the window in pixels
        self.scriptRunning = False   # True while File > Run Script is running
        self.scriptDir = ''          # folder of the last script that was run
        self.programDir = ''         # folder of the last file opened to program
        self.winPos = None    # (x, y) of the window's top-left corner
        self.termTheme = 'light'   # Terminal colours: one of TERM_CHOICES
        self.termBg = CFG_DEFAULTS['terminalBg']       # colours of 'custom'
        self.termFg = CFG_DEFAULTS['terminalFg']
        self.termSelect = CFG_DEFAULTS['terminalSelect']
        self.termFont = CFG_DEFAULTS['terminalFont']
        self.termFontSize = CFG_DEFAULTS['terminalFontSize']
        self.datasheetUrl = datasheet.DEFAULT_URL   # Help > Datasheet
        self.dispMode = 'Binary (b)'   # Read panel display mode (a key of dispmodeOptions)
        self.showPanels = True     # Erase, Program and Read panels shown/hidden

        # Check if %AppData%\Dubrovnik folder exists. If not create one
        appData = os.getenv('APPDATA') or ''
        self.dubrovnikConfigPath = os.path.join(appData, 'Dubrovnik')
        if not os.path.isdir(self.dubrovnikConfigPath):
            os.mkdir(self.dubrovnikConfigPath)

        self.buildFrame()

    def buildFrame(self):
        '''Makes a reusable frame for a connecting to Dubrovnik board'''
        chk = Checkbutton(self, text='Auto connect', variable=self.chk_var)
        chk.grid(row=0, column=0)

        self.combo = ttk.Combobox(
            self, width=10, values=self.portList, postcommand=self.updtPortList)
        self.combo.grid(row=0, column=1, padx=10)

        self.btn2 = Button(self, text='Connect', width=10,
                           command=self.connectPort)
        self.btn2.grid(row=0, column=2, padx=10)

        if self.STANDALONE:
            self.btn3 = Button(self, text='Save Config', width=10,
                               command=self.saveConfig)
            self.btn3.grid(row=0, column=3, padx=10, sticky=E)

        if self.DEBUG:
            self.test_btn = Button(self, text='Testing',
                                   width=10, command=self.testSerComm)
            self.test_btn.grid(row=1, column=0, padx=5, pady=10, columnspan=1)
            self.test_lbl = Label(
                self, text="Debug message:", anchor=W, justify='left')
            self.test_lbl.grid(row=1, column=1, padx=5,
                               pady=10, sticky=EW, columnspan=3)

    def updtPortList(self):
        self.portList = self.comm.findPorts(exit_if_none=False)
        self.combo['values'] = self.portList
        if self.portList:
            self.combo.set(self.portList[0])
        elif self.portStatus == 'disconnected':
            self.combo.set('')
            stsBarComm.config(text='No COM port found: connect the USB cable, '
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
                stsBarComm.config(text=f'Could not open {self.selPort}')
                return
            self.setSerialParams()
            self.btn2.config(text='Disconnect')  # change button label
            self.portStatus = 'connected'  # update connection status
            self.serParams = f'Connected: {self.comPort} ({self.comBaudrate},{self.comBytesize},{self.comParity},{self.comStopbits},{self.comXonXoff})'
            if checkIsFlashPresent:  # allow this part to run only when enabled by func argument
                if self.comm.isFlashPresent():
                    pn = du.get_part_number(self.comm)
                    self.serParams += '    Device: ' + pn
            stsBarComm.config(text=self.serParams)

        elif self.portStatus == 'connected':
            # if connected, disconnect from the current port
            self.disconnectPort(self.selPort)
            self.btn2['text'] = 'Connect'  # update button label
            self.portStatus = 'disconnected'  # update connection status
            stsBarComm.config(text='Disconnected')
        else:
            print('No such port. Try again!!!')
        self.saveConfig()

    def disconnectPort(self, selPort):
        self.comm.disconnect(selPort)
        # print(f"Port: {selPort} disconnected")
        stsBarComm.config(text='No COM port found!')

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
            showerror('Dubrovnik Workbench (Classic) Error',
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
        self.btn2.config(text='Connect')
        stsBarComm.config(text=f'Connection to {lost} lost: the board was '
                         'switched off or unplugged')
        term.displayText(f'*** Connection to {lost} lost (board switched off or '
                         'unplugged). Switch it on, press RESET and click '
                         'Connect. ***')
        if self.scriptRunning:          # a script can't go on without the board
            scriptStop[0] = True

    def deviceDetected(self, partNumber):
        """The board (re)detected its device, e.g. after being switched off and
        on again: show it in the status bar ('' = no device)"""
        if self.portStatus != 'connected':
            return
        base = self.serParams.split('    Device:')[0]
        self.serParams = base + (f'    Device: {partNumber}' if partNumber else '')
        stsBarComm.config(text=self.serParams)

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
        erase.blockSize.set(erase.blockSizes[0])
        erase.startAddr.set('0')
        erase.numBlocks.set('1')
        program.pattern.set('cafe0000')
        program.increment.set('1')
        program.start_addr.set('0')
        program.length.set('100')
        read.spiMode.set(read.spiModes[0])
        read.startAddr.set('0')
        read.readLength.set('100')

    def loadDefaultSettings(self):
        """Resets everything: connection settings and the entry boxes"""
        self.chk_var.set(0)
        self.autoConnect = 0
        self.selPort = ''
        self.lastUsedPort = ''
        self.loadDefaultParams()

    def saveConfig(self, params=False):
        """Saves the settings that are remembered automatically (connection,
        window, ...). The entry-box values of the Erase, Program and Read
        panels are saved only when params=True (File > Parameters > Save);
        otherwise the values already stored in the file are kept."""
        cfgFile = os.path.join(self.dubrovnikConfigPath, 'dubrovnik.cfg')
        # Start from the existing file: it keeps the stored values and any
        # settings written by other apps (an unreadable file is replaced).
        cfg, _ = cfgfile.read_json(cfgFile)
        cfg.update({'autoConnect': self.chk_var.get(),
                    'lastUsedPort': self.selPort,
                    'terminalTheme': self.termTheme,
                    'terminalBg': self.termBg,
                    'terminalFg': self.termFg,
                    'terminalSelect': self.termSelect,
                    'terminalFont': self.termFont,
                    'terminalFontSize': self.termFontSize,
                    'datasheetUrl': self.datasheetUrl,
                    'showPanels': self.showPanels,
                    'displayMode': self.dispMode,
                    'scriptFolder': self.scriptDir,
                    'programFolder': self.programDir})
        # own keys: the Workbench stores its size in different (scaled) units
        if self.winSize:
            cfg['mainWindowWidth'], cfg['mainWindowHeight'] = self.winSize
        if self.winPos:
            cfg['mainWindowX'], cfg['mainWindowY'] = self.winPos
        if params:
            cfg.update({'eraseBlkSize': str(erase.blockSize.get()),
                        'eraseStartAddr': str(erase.startAddr.get()),
                        'eraseNumBlocks': str(erase.numBlocks.get()),
                        'progPattern': program.pattern.get(),
                        'progIncrement': program.increment.get(),
                        'progStartAddr': program.start_addr.get(),
                        'progLength': program.length.get(),
                        'readSpiMode': read.spiMode.get(),
                        'readStartAddr': read.startAddr.get(),
                        'readLength': read.readLength.get()})
        # the Workbench now has its own file; drop its old entries
        for key in ('windowWidth', 'windowHeight', 'windowX', 'windowY',
                    'appearance'):
            cfg.pop(key, None)
        cfgfile.write_json(cfgFile, cfg)

    def loadConfig(self, prefs=True, params=True):
        """Loads the settings file: the remembered settings (prefs) and/or the
        stored entry-box values (params). A missing or damaged file, or a bad
        value in it, falls back to defaults; this never stops the app."""
        cfgFile = os.path.join(self.dubrovnikConfigPath, 'dubrovnik.cfg')
        cfg, status = cfgfile.read_json(cfgFile)
        if status != 'ok':          # first run, or unreadable (kept as .bad)
            self.loadDefaultSettings()
            self.saveConfig(params=True)
            return
        v = cfgfile.clean(cfg, CFG_DEFAULTS)
        for key, allowed in (('eraseBlkSize', erase.blockSizes),
                             ('readSpiMode', read.spiModes),
                             ('displayMode', tuple(read.dispmodeOptions)),
                             ('terminalTheme', TERM_CHOICES)):
            if v[key] not in allowed:
                v[key] = CFG_DEFAULTS[key]
        termstyle.repair(v, CFG_DEFAULTS)
        if prefs:
            self.autoConnect = v['autoConnect']
            self.chk_var.set(self.autoConnect)
            self.selPort = v['lastUsedPort']
            self.lastUsedPort = self.selPort
            self.termTheme = v['terminalTheme']
            self.termBg, self.termFg = v['terminalBg'], v['terminalFg']
            self.termSelect = v['terminalSelect']
            self.termFont = v['terminalFont']
            self.termFontSize = v['terminalFontSize']
            self.datasheetUrl = datasheet.clean_url(v['datasheetUrl'])
            self.showPanels = v['showPanels']
            self.dispMode = v['displayMode']
            read.applyDispMode(self.dispMode)
            self.scriptDir = v['scriptFolder'] if os.path.isdir(v['scriptFolder']) else ''
            self.programDir = (v['programFolder']
                               if os.path.isdir(v['programFolder']) else '')
            self.winSize = cfgfile.int_pair(cfg, 'mainWindowWidth',
                                            'mainWindowHeight', 200, 20000)
            self.winPos = cfgfile.int_pair(cfg, 'mainWindowX', 'mainWindowY',
                                           -32000, 32000)
        if params:
            erase.blockSize.set(v['eraseBlkSize'])
            erase.startAddr.set(v['eraseStartAddr'])
            erase.numBlocks.set(v['eraseNumBlocks'])
            program.pattern.set(v['progPattern'])
            program.increment.set(v['progIncrement'])
            program.start_addr.set(v['progStartAddr'])
            program.length.set(v['progLength'])
            read.spiMode.set(v['readSpiMode'])
            read.startAddr.set(v['readStartAddr'])
            read.readLength.set(v['readLength'])

    def testSerComm(self):
        serParams = '%s, baud=%d, bytes=%1d,\nparity=%s, stop=%1d, protocol=%s' \
            % (self.comPort, self.comBaudrate, self.comBytesize, self.comParity, self.comStopbits, self.comXonXoff)
        self.test_lbl.config(text=serParams)


class ProgramFrame(LabelFrame):
    startAddr = 0
    dataLen = 0
    endAddr = 0
    pattn = 'cafe0000'
    incr = '1'
    image = None            # firmware_image.Image loaded with Open
    imageName = ''

    def __init__(self, parent=None, DEBUG=False):
        LabelFrame.__init__(self, parent, text='Program', padx=5, pady=10)
        # self.pack(side=TOP, anchor=NW, padx=10, pady=10)
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
        rb_file = Radiobutton(self, text='Use Pattern', variable=self.progModeVar,
                              value=self.progModeList[0], command=self.grayOutEntry)
        rb_file.grid(row=1, column=0, padx=10, pady=2, sticky=W)

        rb_pattn = Radiobutton(self, text='Load from File', variable=self.progModeVar,
                               value=self.progModeList[1], command=self.grayOutEntry)
        rb_pattn.grid(row=2, column=0, padx=10, pady=2, sticky=W)

        lbl1_prog = self.lbl1_prog = Label(self, text='Pattern: 0x')
        self.labelFg = lbl1_prog.cget('fg')       # normal label colour
        lbl1_prog.grid(row=0, column=1, padx=5, pady=5, sticky=E)
        self.ent1_prog = Entry(self, textvariable=self.pattern)
        self.ent1_prog.grid(row=0, column=2)
        self.pattern.set('caba0000')

        lbl2_prog = self.lbl2_prog = Label(self, text='Increment: 0x')
        lbl2_prog.grid(row=1, column=1, padx=5, pady=5, sticky=E)
        self.ent2_prog = Entry(self, textvariable=self.increment)
        self.ent2_prog.grid(row=1, column=2)
        self.increment.set('1')

        lbl3_prog = self.lbl3_prog = Label(self, text='Start Address: 0x')
        lbl3_prog.grid(row=2, column=1, padx=5, pady=5, sticky=E)
        self.ent3_prog = Entry(self, textvariable=self.start_addr)
        self.ent3_prog.grid(row=2, column=2)
        self.start_addr.set('60')

        lbl4_prog = self.lbl4_prog = Label(self, text='Length: 0x')
        lbl4_prog.grid(row=3, column=1, padx=5, pady=5, sticky=E)
        self.ent4_prog = Entry(self, textvariable=self.length)
        self.ent4_prog.grid(row=3, column=2)
        self.length.set('250')

        self.btn_openFile = Button(
            self, text='Open', width=10, command=self.openFile, state=DISABLED)
        self.btn_openFile.grid(row=5, column=0, padx=10, sticky=S, pady=(2, 10))
        self.btn_progFile = Button(
            self, text='Program', width=10, command=self.program)
        self.btn_progFile.grid(row=5, column=1, padx=10, sticky=S, pady=(2, 10))
        self.grid_rowconfigure(5, weight=1)    # button row sits at the panel bottom
        self.btn_progVer = Button(self, text='Prog/Verify',
                                  width=10, command=self.progVerify, state=DISABLED)
        self.btn_progVer.grid(row=5, column=2, padx=10, sticky=S, pady=(2, 10))

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
            label.config(fg='gray50' if fileMode else self.labelFg)
            entry.config(state=DISABLED if fileMode else NORMAL)
        self.btn_openFile.config(state=NORMAL if fileMode else DISABLED)
        self.lbl3_prog.config(
            text='Offset: 0x' if fileMode else 'Start Address: 0x')

    def program(self):
        if serCom.scriptBusy():
            return
        if not serCom.checkConnection():  # check if board is connected
            return
        try:
            self.get_states()
        except ValueError as e:
            showerror('Program', str(e))
            return
        if self.progModeVar.get() == 'pattern':
            du.page_program(
                self.comm, startAddr, dataLen, pattn, incr)
            term.tprint(du.textToDisplay[:-1])
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
                    du.data_program(comm, data, target, progress)
                    messages.put(('tprint', du.textToDisplay[:-1]))
                    base += len(data)
                result['finished'] = True
            except ProgramCancelled:
                result['cancelled'] = True
            except BaseException as e:      # incl. SystemExit from a comm error
                result['error'] = f'{type(e).__name__}: {e}'

        dialog = ProgressDialog('Programming', total)
        serCom.scriptRunning = True     # blocks the panels and the Terminal
        term.cmdInProgress = True       # and the background serial reader
        scriptStop[0] = False           # Esc or a lost connection cancels too
        worker = threading.Thread(target=work, daemon=True)
        worker.start()

        def poll():
            while True:
                try:
                    kind, text = messages.get_nowait()
                except queue.Empty:
                    break
                getattr(term, kind)(text)
            if dialog.cancelled or scriptStop[0]:
                state['cancel'] = True
            dialog.show(state['text'], state['done'])
            if worker.is_alive():
                root.after(100, poll)
                return
            while not messages.empty():     # text posted just before the end
                kind, text = messages.get_nowait()
                getattr(term, kind)(text)
            term.cmdInProgress = False
            serCom.scriptRunning = False
            dialog.close()
            if result['cancelled']:
                term.displayText('*** Programming cancelled; the device may be '
                                 'partly programmed. ***\n')
            elif result['error']:
                term.displayText(f'*** Programming stopped: {result["error"]}. '
                                 'The device may be partly programmed. ***\n')
            elif count > 1:
                term.displayText(f'Programmed {count} segments, '
                                 f'{self.image.size} bytes in total.\n')
        root.after(100, poll)

    def progVerify(self):
        pass

    def openFile(self):
        folder = serCom.programDir
        filename = askopenfilename(
            title='Select File to Program',
            initialdir=folder if os.path.isdir(folder) else os.getcwd(),
            filetypes=firmware_image.FILE_TYPES)
        if not filename:             # dialog cancelled
            return False
        serCom.programDir = os.path.dirname(filename)   # start here next time
        serCom.saveConfig()
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
        """Tells the user what was loaded (Terminal and status bar)"""
        term.displayText(f'Loaded {self.imageName}: {self.image.describe()}\n')
        if len(self.image.segments) > 1:
            term.displayText(self.rangesText() + '\n')
        term.displayText('Addresses are used as in the file, plus the Offset '
                         '(File > Program Loaded File, or the Program panel). '
                         'Erase first if needed.\n')
        showStatus(f'Loaded {self.imageName}: {self.image.describe()}', 8000)

    def closeFile(self):
        self.image, self.imageName = None, ''


class EraseFrame(LabelFrame):
    def __init__(self, parent=None, DEBUG=False):
        LabelFrame.__init__(self, parent, text='Erase',
                            relief=GROOVE, padx=10, pady=10)
        # self.pack(side=TOP, anchor=NW, padx=10, pady=10)
        self.grid()
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
        # ersfrm = LabelFrame(self, parent).pack(side=LEFT, anchor=NW, padx=10,pady=10)
        rb1_ers = Radiobutton(self, text='4kB',
                              variable=self.blockSize, value=self.blockSizes[0])
        rb1_ers.grid(row=0, column=0, padx=10, pady=2, sticky=W)
        rb2_ers = Radiobutton(self, text='32kB',
                              variable=self.blockSize, value=self.blockSizes[1])
        rb2_ers.grid(row=1, column=0, padx=10, pady=2, sticky=W)
        rb3_ers = Radiobutton(self, text='64kB',
                              variable=self.blockSize, value=self.blockSizes[2])
        rb3_ers.grid(row=2, column=0, padx=10, pady=2, sticky=W)
        rb4_ers = Radiobutton(self, text='Chip',
                              variable=self.blockSize, value=self.blockSizes[3])
        rb4_ers.grid(row=3, column=0, padx=10, pady=2, sticky=W)

        lbl_ers = Label(self, text='Start Address:  0x')
        lbl_ers.grid(row=0, column=1, padx=10, pady=2, sticky=E)
        ent1_ers = Entry(self, textvariable=self.startAddr)
        ent1_ers.grid(row=0, column=2, sticky=W)

        self.startAddr.set('0')

        lbl2_ers = Label(self, text='Num. Blocks:    ')
        lbl2_ers.grid(row=1, column=1, padx=10, pady=2, sticky=E)
        ent2_ers = Entry(self, textvariable=self.numBlocks)
        ent2_ers.grid(row=1, column=2, sticky=W)

        self.numBlocks.set('3')

        btn2_ers = Button(self, text='Erase', width=12,
                          justify='center', command=self.blockErase)
        btn2_ers.grid(row=4, column=2, sticky='sew', pady=(2, 10))
        self.grid_rowconfigure(4, weight=1)    # button row sits at the panel bottom

        if self.DEBUG:
            lbl4_ers = Label(self, text='Results here:')
            lbl4_ers.grid(row=4, column=0, sticky=E)

            quit_btn_ers = Button(self, text='Erase test',
                                  width=12, command=self.erase_test)
            quit_btn_ers.grid(row=3, column=1, padx=2, pady=2)

    def blockErase(self):
        if serCom.scriptBusy():
            return
        if not serCom.checkConnection():  # check if board is connected
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
            term.tprint(f'Erasing {num_blocks} {block_size}kB block(s) from address {startAddr:x}',
                        printOn='guiConsole')
            du.block_erase(
                self.comm, block_size, start_addr, num_blocks)
        else:
            term.tprint('Erasing chip', printOn='guiConsole')
            du.block_erase(self.comm, blkSzStr)

        term.tprint(du.textToDisplay[:-1])

    def erase_test(self):
        print(f'Selected Erase Block Size : {self.blockSize.get()}')
        print(f'Start Address             : {self.startAddr.get()}')
        print(f'Number of Blocks          : {self.numBlocks.get()}')
        print('\n')


class ReadFrame(LabelFrame):
    def __init__(self, parent=None, DEBUG=False):
        LabelFrame.__init__(self, parent, text='Read',
                            relief=GROOVE, padx=10, pady=10)
        # self.pack(side=TOP, anchor=NW, padx=10, pady=10)
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
        '''Makes a reusable frame for a flash erase operation'''
        # ersfrm = LabelFrame(self, parent).pack(side=LEFT, anchor=NW, padx=10,pady=10)
        rb1_read = Radiobutton(self, text=self.spiModes[0],
                               variable=self.spiMode, value=self.spiModes[0])
        rb1_read.grid(row=0, column=0, padx=10, pady=2, sticky=W)
        rb2_read = Radiobutton(self, text=self.spiModes[1],
                               variable=self.spiMode, value=self.spiModes[1])
        rb2_read.grid(row=1, column=0, padx=10, pady=2, sticky=W)
        rb3_read = Radiobutton(self, text=self.spiModes[2],
                               variable=self.spiMode, value=self.spiModes[2])
        rb3_read.grid(row=2, column=0, padx=10, pady=2, sticky=W)
        rb4_read = Radiobutton(self, text=self.spiModes[3],
                               variable=self.spiMode, value=self.spiModes[3])
        rb4_read.grid(row=3, column=0, padx=10, pady=2, sticky=W)
        rb5_read = Radiobutton(self, text=self.spiModes[4],
                               variable=self.spiMode, value=self.spiModes[4],
                               state=DISABLED)  # not supported yet
        rb5_read.grid(row=4, column=0, padx=10, pady=2, sticky=W)
        rb6_read = Radiobutton(self, text=self.spiModes[5],
                               variable=self.spiMode, value=self.spiModes[5],
                               state=DISABLED)  # not supported yet
        rb6_read.grid(row=5, column=0, padx=10, pady=2, sticky=NW)

        lbl_read = Label(self, text='Start Address:  0x')
        lbl_read.grid(row=0, column=1, padx=10, pady=2, sticky=E)
        ent1_read = Entry(self, textvariable=self.startAddr)
        ent1_read.grid(row=0, column=2, sticky=EW)

        self.startAddr.set('0')
        self.readLength.set('200')

        lbl2_read = Label(self, text='Length:  0x')
        lbl2_read.grid(row=1, column=1, padx=10, pady=2, sticky=E)
        ent2_read = Entry(self, textvariable=self.readLength)
        ent2_read.grid(row=1, column=2, sticky=EW)

        # self.spiMode.set('0')

        dispmode_lbl = Label(self, text='Display Mode: ')
        dispmode_lbl.grid(row=4, column=1, padx=5, sticky="E")

        # add "HexView (h)": 'h'}
        self.dispmodeOptions = {"Binary (b)": 'b', "DWord (w)": 'w'}
        options = list(self.dispmodeOptions.keys())
        self.dispmode_cb = ttk.Combobox(
            self, width=16, values=options, state='readonly')
        self.dispmode_cb.grid(row=4, column=2, sticky=EW)

        self.dispmode_cb.set(options[0])
        du.dispmode = self.dispmodeOptions[options[0]]

        self.dispmode_cb.bind('<<ComboboxSelected>>', self.dispmode_cb_updated)

        btn1_read = Button(self, text='Read', width=12,
                           justify='center', command=self.readFlash)
        btn1_read.grid(row=5, column=2, sticky='sew', pady=(2, 10))
        self.grid_rowconfigure(5, weight=1)    # button row sits at the panel bottom

        if self.DEBUG:
            btn2_read = Button(self, text='Read test',
                               width=12, command=self.readFlash)
            btn2_read.grid(row=5, column=1, padx=2, pady=2)

    def applyDispMode(self, label):
        """Selects a display mode (a key of dispmodeOptions) in the combo box"""
        self.dispmode_cb.set(label)
        du.dispmode = self.dispmodeOptions[label]

    def dispmode_cb_updated(self, _event):
        dispModeSelKey = self.dispmode_cb.get()  # get the selected item in Combo
        # assign the associated value to dispmode
        mode = self.dispmodeOptions[dispModeSelKey]
        du.dispmode = mode  # update dispmode in class Dubrovnik
        self.modeKeys = list(self.dispmodeOptions.keys())
        if mode == 'b':
            self.dispmode_cb.set(self.modeKeys[0])
        elif mode == 'w':
            self.dispmode_cb.set(self.modeKeys[1])
        else:
            # change it to [2] once hexView 'h' is implemented
            self.dispmode_cb.set(self.modeKeys[0])
        serCom.dispMode = self.dispmode_cb.get()    # remembered automatically
        serCom.saveConfig()

    def readFlash(self):
        if serCom.scriptBusy():
            return
        if not serCom.checkConnection():  # check if board is connected
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
            du.read_mode(self.comm, self.spiMode.get(),
                         start_addr=readStartAddr, length=readLen, echo=0)
        except ValueError as e:
            showerror('Read', str(e))
            return
        term.tprint(du.textToDisplay[:-1], printOn='guiConsole')


class Terminal(LabelFrame):
    def __init__(self, parent=None):
        LabelFrame.__init__(self, parent, text='Terminal',
                            relief=GROOVE, padx=10, pady=10)
        self.comm = None
        self.history = []
        self.historyIndex = 0
        # CM TODO: check if needed. displayText implemented differently
        self.textToDisplay = None
        # Async serial polling: set True while onReturnKey owns the serial port
        # so the poller doesn't race with comm.send()/response().
        self.cmdInProgress = False
        self.pollIntervalMs = 100

        # clear_btn = Button(self, text="Clear Display", command=self.clear)
        # clear_btn.grid(row=0, column=0, padx=10, sticky='W')

        self.txt = scrolledtext.ScrolledText(
            self, wrap=CHAR, width=80, height=24, font=("Consolas", 11))
        self.txt.grid(row=1, column=0, columnspan=99,
                      pady=10, padx=10, sticky="NSEW")
        self.onZoom = None       # set by the app: onZoom(+1 or -1), Ctrl + wheel
        self.applyColors(TERM_THEMES['light'])

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
        self.txt.configure(font=(family, size))

    def applyColors(self, t):
        """Sets the Terminal colours; t has the keys bg, fg and select"""
        self.txt.configure(bg=t['bg'], fg=t['fg'], insertbackground=t['fg'],
                           selectbackground=t['select'], selectforeground=t['fg'])

    def showContextMenu(self, event):
        try:
            # one entry only: make it easy to hit
            self.ctxMenu.configure(font=('Segoe UI', 11))
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
                    serCom.connectionLost()
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
            serCom.deviceDetected('')
            self.bootBuf = self.bootBuf.split('Detecting flash part')[-1]
        m = re.search(r'Part info:\s*(\S+)\s', self.bootBuf)  # whole word received
        if m:
            serCom.deviceDetected(m.group(1))
            self.bootBuf = ''

    def displayText(self, text):
        self.txt.insert(END, '\n' + text)
        self.txt.insert(END, '\n' + PROMPT)
        self.txt.mark_set(INSERT, END)
        self.txt.see(INSERT)

    def onReturnKey(self, _event):
        if serCom.scriptRunning:
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
            du.textToDisplay = ""
        else:
            print(text)
            # term.displayText(text)
            self.displayText(text)
            du.textToDisplay = ""

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


if __name__ == "__main__":

    # def updtStsBar(statusMsg):
    #     print(statusMsg)
    #     stsBarComm.config(text=statusMsg)

    def showAbout():
        aboutMsg = f'''
                   *************************************
                   *** Dubrovnik Workbench (Classic) ***
                   *************************************

                   Version {APP_VERSION}

                   Authors:
                   Csaba Moldvai (System/Board design, GUI)
                   Eyal Barzilay (Tiberias flash support software)'''
        showinfo('About', aboutMsg)

    root = Tk()
    root.title(f'Dubrovnik Workbench (Classic) {APP_VERSION}')

    comm = boardcom.BoardComm()   # create an instance of class Comm
    du = dubrovnik.Dubrovnik()

    portList = comm.findPorts(exit_if_none=False)   # may be empty: no board yet

    # TODO Eventually migrate to a format where MainWindow is in itw own class
    # window = MainWindow(root)

# *******************************************
# ****** Serial Communications Panel ********
# *******************************************
    serCom = SerComFrame(root, DEBUG=False)  # invoking the class
    # serCom.pack(side=TOP, fill=BOTH)
    serCom.grid_propagate(0)
    serCom.config(width=350, height=60, bd=PANEL_BORDER, relief=GROOVE)
    serCom.grid(row=0, column=0, padx=10, pady=4, sticky=NW)
    if portList:
        serCom.combo.set(portList[0])
    serCom.comm = comm
    serCom.checkLink()      # notices when the board is switched off

# ******************************
# ****** Erase Panel   *********
# ******************************
    erase = EraseFrame(root, DEBUG=False)  # invoking the class
    # erase.pack(side=LEFT, fill=BOTH)
    erase.config(bd=PANEL_BORDER, relief=GROOVE)
    erase.grid(row=1, column=0, padx=10, pady=4, sticky=NSEW)
    erase.comm = comm     # initializeing self.com in Erase class

# ******************************
# ****** Program Panel *********
# ******************************
    # TODO rename program to progFrm
    program = ProgramFrame(root, DEBUG=False)  # invoking the class
    # program.pack(side=LEFT, fill=BOTH)
    program.config(bd=PANEL_BORDER, relief=GROOVE)
    program.grid(row=1, column=1, padx=10, pady=4, sticky=NSEW)
    program.comm = comm   # initializeing self.com in Program class

# ***************************
# ****** Read Panel *********
# ***************************
    read = ReadFrame(root, DEBUG=False)  # invoking the class
    # read.pack(side=LEFT, fill=BOTH)
    read.config(bd=PANEL_BORDER, relief=GROOVE)
    read.grid(row=1, column=2, padx=10, pady=4, sticky=NSEW)
    read.comm = comm     # initializeing self.com in ReadFrame class

    # All three panels get the same height: as tall as the tallest one needs, so
    # no button is squished. Widths stay fixed.
    root.update_idletasks()
    panelH = max(f.winfo_reqheight() for f in (erase, program, read))
    for panel, panelW in ((erase, 350), (program, 380), (read, 380)):
        panel.grid_propagate(0)
        panel.config(width=panelW, height=panelH)

# ***********************************
# ******** Terminal Window **********
# ***********************************
    term = Terminal(root)
    term.grid(row=2, column=0, padx=10, pady=4, columnspan=4, sticky=NSEW)
    term.grid_columnconfigure(0, weight=1)
    term.grid_rowconfigure(1, weight=1)  # txt widget lives at row 1
    term.comm = comm     # initializeing self.com in Erase class

    # Let the terminal row absorb all extra vertical space.
    root.grid_rowconfigure(2, weight=1)
    # Panels stay at their natural width, locked to the left; only the spacer
    # column 3 absorbs extra horizontal space (the Terminal grows with it).
    for col in (0, 1, 2):
        root.grid_columnconfigure(col, weight=0)
    root.grid_columnconfigure(3, weight=1)

# ***************************
# ****** Status Bar *********
# ***************************
    stsBarComm = Label(root, text='Not connected', font=(
        "Helvetica", 9), anchor=W, justify=LEFT, pady=2)
    stsBarComm.config(bd=1, relief=SUNKEN)
    # stsBarComm.pack(side=BOTTOM, fill=X, anchor=W, padx=10, pady=10)
    stsBarComm.grid_propagate(0)
    stsBarComm.grid(row=4, column=0, padx=10, pady=4,
                    columnspan=4, sticky=EW)

    # stsBarRight = Label(root, text='Hello', width=10, font=(
    #     "Helvetica", 9), anchor=W, justify=RIGHT, pady=2)
    # stsBarRight.config(bd=1, relief=SUNKEN)
    # # stsBarComm.pack(side=BOTTOM, fill=X, anchor=W, padx=10, pady=10)
    # stsBarRight.grid_propagate(0)
    # stsBarRight.grid(row=4, column=1, padx=10, pady=4,sticky='EW')

    # ############ MENU
    my_menu = Menu(root)
    root.config(menu=my_menu)

    file_menu = Menu(my_menu, tearoff=False)
    my_menu.add_cascade(label="File", menu=file_menu)
    file_menu.add_command(label="Open Firmware File...", accelerator="Ctrl+O",
                          command=lambda: openForProgramming())
    file_menu.add_command(label="Program Loaded File", accelerator="Ctrl+P",
                          command=lambda: programLoadedFile())
    file_menu.add_command(label="No file loaded", state=DISABLED)
    file_menu.add_command(label="Close File", command=lambda: closeLoadedFile())
    file_menu.add_separator()
    scripts_menu = Menu(file_menu, tearoff=False)
    file_menu.add_cascade(label="Scripts", menu=scripts_menu)
    scripts_menu.add_command(label="Run Command Script...",
                             command=lambda: runScript())
    scripts_menu.add_command(label="Run Python Script...",
                             command=lambda: runPythonScript())
    scripts_menu.add_separator()
    scripts_menu.add_command(label="Stop Script  (Esc)",
                             command=lambda: stopScript())
    file_menu.add_command(label="Save Terminal Log...",
                          command=lambda: saveTerminalLog())
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=lambda: onClose())

    tools_menu = Menu(my_menu, tearoff=False,
                      postcommand=lambda: refreshTools())
    my_menu.add_cascade(label="Tools", menu=tools_menu)

    # View menu: panel visibility and Terminal colours (radio items mark the
    # current choice)
    view_menu = Menu(my_menu, tearoff=False)
    my_menu.add_cascade(label="View", menu=view_menu)
    panels_menu = Menu(view_menu, tearoff=False)
    view_menu.add_cascade(label="Panels (Erase/Program/Read)", menu=panels_menu)
    view_menu.add_separator()
    view_menu.add_command(label="Terminal...",
                          command=lambda: showTerminalDialog())

    panelsVar = StringVar(value='show' if serCom.showPanels else 'hide')

    def layoutPanels():
        """Shows or hides the three panels together (serCom.showPanels).
        grid_remove() remembers the grid options, so grid() restores them."""
        for frame in (erase, program, read):
            if serCom.showPanels:
                frame.grid()
            else:
                frame.grid_remove()

    def syncPanels():
        """Applies serCom.showPanels to the menu mark and the layout"""
        panelsVar.set('show' if serCom.showPanels else 'hide')
        layoutPanels()

    def onPanelToggle():
        """A Panels menu item was clicked: re-layout, then change the window
        height by the height gained or lost so the Terminal keeps its size"""
        serCom.showPanels = panelsVar.get() == 'show'
        root.update_idletasks()
        # measure before re-laying out: a window that was never given an
        # explicit size follows its requested size by itself
        before, curW, curH = (root.winfo_reqheight(), root.winfo_width(),
                              root.winfo_height())
        layoutPanels()
        root.update_idletasks()
        minW = min(root.winfo_reqwidth(), scrW - marginW)
        root.minsize(width=minW, height=1)
        h = curH + root.winfo_reqheight() - before
        h = max(1, min(h, scrH - marginH))
        root.geometry(f'{max(minW, curW)}x{h}')
        serCom.saveConfig()

    def termColors():
        """The Terminal colours (bg, fg, select) of the chosen theme"""
        if serCom.termTheme == 'custom':
            return dict(bg=serCom.termBg, fg=serCom.termFg,
                        select=serCom.termSelect)
        return TERM_THEMES[serCom.termTheme]

    def applyTerminal():
        """Applies the Terminal look (e.g. just loaded from the config file)"""
        term.applyColors(termColors())
        term.setFont(serCom.termFont, serCom.termFontSize)

    zoomState = dict(save=None, restore=None, old=None)

    def zoomTerminal(step):
        """Ctrl + mouse wheel: bigger or smaller Terminal text. The setting is
        saved shortly after the wheel stops."""
        size = termstyle.clamp_size(serCom.termFontSize + step)
        if size != serCom.termFontSize:
            serCom.termFontSize = size
            applyTerminal()
            if zoomState['save']:
                root.after_cancel(zoomState['save'])
            zoomState['save'] = root.after(600, serCom.saveConfig)
        # show the size in the status bar, then put the old text back
        if zoomState['restore']:
            root.after_cancel(zoomState['restore'])
        else:
            zoomState['old'] = stsBarComm.cget('text')
        stsBarComm.configure(text=f'Terminal text size {size}')

        def restore():
            stsBarComm.configure(text=zoomState['old'])
            zoomState['restore'] = None
        zoomState['restore'] = root.after(1500, restore)

    term.onZoom = zoomTerminal

    fontCache = []
    termDialog = {}

    def showTerminalDialog():
        """View > Terminal...: theme, colours, font and size with a preview.
        Changes show in the Terminal at once; Cancel puts the old look back."""
        if termDialog.get('win') is not None and termDialog['win'].winfo_exists():
            termDialog['win'].lift()
            termDialog['win'].focus_set()
            return
        saved = (serCom.termTheme, serCom.termBg, serCom.termFg,
                 serCom.termSelect, serCom.termFont, serCom.termFontSize)
        dlg = tk.Toplevel(root)
        termDialog['win'] = dlg
        dlg.title('Terminal')
        dlg.resizable(False, False)
        dlg.transient(root)
        themes = (('Light', 'light'), ('Dark', 'dark'), ('Custom', 'custom'))
        if not fontCache:
            fontCache.extend(termstyle.monospaced_fonts(root))
        fonts = list(fontCache)
        if serCom.termFont not in fonts:
            fonts.insert(0, serCom.termFont)

        def label(row, text):
            ttk.Label(dlg, text=text).grid(row=row, column=0, padx=(16, 8),
                                           pady=5, sticky='w')

        label(0, 'Theme')
        themeBox = ttk.Combobox(dlg, values=[t[0] for t in themes],
                                state='readonly', width=26)
        themeBox.grid(row=0, column=1, columnspan=3, padx=(0, 16), pady=5,
                      sticky='w')
        themeBox.bind('<<ComboboxSelected>>',
                      lambda _e: pickTheme(themeBox.get()))

        swatches = {}
        hexEntries = {}
        for row, (key, text, attr) in enumerate((
                ('bg', 'Background', 'termBg'), ('fg', 'Text', 'termFg'),
                ('select', 'Selection', 'termSelect')), start=1):
            label(row, text)
            swatches[key] = tk.Button(
                dlg, width=6, relief='solid', bd=1,
                command=lambda k=key, a=attr: chooseColour(k, a))
            swatches[key].grid(row=row, column=1, padx=(0, 8), pady=5,
                               sticky='w')
            entry = ttk.Entry(dlg, width=12)
            entry.grid(row=row, column=2, columnspan=2, padx=(0, 16), pady=5,
                       sticky='w')
            entry.bind('<Return>', lambda _e, a=attr, k=key: typedColour(k, a))
            entry.bind('<FocusOut>', lambda _e, a=attr, k=key: typedColour(k, a))
            hexEntries[key] = entry

        label(4, 'Font')
        fontBox = ttk.Combobox(dlg, values=fonts, state='readonly', width=26)
        fontBox.grid(row=4, column=1, columnspan=3, padx=(0, 16), pady=5,
                     sticky='w')
        fontBox.bind('<<ComboboxSelected>>', lambda _e: pickFont(fontBox.get()))

        label(5, 'Size')
        ttk.Button(dlg, text='-', width=3,
                   command=lambda: setSize(serCom.termFontSize - 1)
                   ).grid(row=5, column=1, padx=(0, 4), pady=5, sticky='w')
        sizeEntry = ttk.Entry(dlg, width=5, justify='center')
        sizeEntry.grid(row=5, column=2, pady=5, sticky='w')
        ttk.Button(dlg, text='+', width=3,
                   command=lambda: setSize(serCom.termFontSize + 1)
                   ).grid(row=5, column=3, padx=(4, 16), pady=5, sticky='w')
        sizeEntry.bind('<Return>', lambda _e: typedSize())
        sizeEntry.bind('<FocusOut>', lambda _e: typedSize())

        preview = tk.Text(dlg, height=5, width=44, wrap='none', bd=1,
                          relief='solid')
        preview.grid(row=6, column=0, columnspan=4, padx=16, pady=(10, 4),
                     sticky='ew')
        preview.insert('1.0', '>>> freq 64\nFrequency set to 64 MHz\n'
                       '0000: CA FE 00 00 ')
        preview.insert('end', 'DE AD BE EF', 'picked')
        preview.configure(state='disabled', cursor='arrow')

        def refresh():
            if not dlg.winfo_exists():
                return
            colours = termColors()
            for key, swatch in swatches.items():
                swatch.configure(bg=colours[key], activebackground=colours[key])
                hexEntries[key].delete(0, END)
                hexEntries[key].insert(0, colours[key].upper())
            themeBox.set(next(n for n, v in themes if v == serCom.termTheme))
            fontBox.set(serCom.termFont)
            sizeEntry.delete(0, END)
            sizeEntry.insert(0, str(serCom.termFontSize))
            preview.configure(bg=colours['bg'], fg=colours['fg'],
                              font=(serCom.termFont, serCom.termFontSize))
            preview.tag_configure('picked', background=colours['select'],
                                  foreground=colours['fg'])
            applyTerminal()

        def pickTheme(name):
            serCom.termTheme = dict(themes)[name]
            refresh()

        def setColour(attr, value):
            # editing any colour switches to the Custom theme, starting from
            # the colours that are shown now
            colours = termColors()
            serCom.termBg, serCom.termFg = colours['bg'], colours['fg']
            serCom.termSelect = colours['select']
            setattr(serCom, attr, value.lower())
            serCom.termTheme = 'custom'
            refresh()

        def chooseColour(key, attr):
            _rgb, value = askcolor(color=termColors()[key], parent=dlg,
                                   title='Terminal colour')
            if value:
                setColour(attr, value)

        def typedColour(key, attr):
            if not dlg.winfo_exists():
                return
            text = hexEntries[key].get().strip()
            if re.fullmatch(r'[0-9a-fA-F]{6}', text):
                text = '#' + text
            if (HEX_COLOR.fullmatch(text)
                    and text.lower() != termColors()[key].lower()):
                setColour(attr, text)
            else:
                refresh()      # unchanged or not a colour: show the real value

        def pickFont(name):
            serCom.termFont = name
            refresh()

        def setSize(value):
            serCom.termFontSize = termstyle.clamp_size(value)
            refresh()

        def typedSize():
            if not dlg.winfo_exists():
                return
            try:
                setSize(int(sizeEntry.get().strip()))
            except ValueError:
                refresh()

        def reset():
            serCom.termTheme = 'light'
            serCom.termBg = CFG_DEFAULTS['terminalBg']
            serCom.termFg = CFG_DEFAULTS['terminalFg']
            serCom.termSelect = CFG_DEFAULTS['terminalSelect']
            serCom.termFont = CFG_DEFAULTS['terminalFont']
            serCom.termFontSize = CFG_DEFAULTS['terminalFontSize']
            refresh()

        def ok():
            serCom.saveConfig()
            dlg.destroy()

        def cancel():
            (serCom.termTheme, serCom.termBg, serCom.termFg, serCom.termSelect,
             serCom.termFont, serCom.termFontSize) = saved
            applyTerminal()
            dlg.destroy()

        bar = ttk.Frame(dlg)
        bar.grid(row=7, column=0, columnspan=4, padx=16, pady=(8, 14),
                 sticky='ew')
        bar.grid_columnconfigure(0, weight=1)
        ttk.Button(bar, text='Reset to defaults', command=reset
                   ).grid(row=0, column=0, sticky='w')
        ttk.Button(bar, text='OK', width=9, command=ok
                   ).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(bar, text='Cancel', width=9, command=cancel
                   ).grid(row=0, column=2, padx=(8, 0))
        dlg.bind('<Escape>', lambda _e: cancel())
        dlg.protocol('WM_DELETE_WINDOW', cancel)

        refresh()
        dlg.update_idletasks()
        x = root.winfo_x() + (root.winfo_width() - dlg.winfo_width()) // 2
        y = root.winfo_y() + (root.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f'+{max(x, 0)}+{max(y, 0)}')
        dlg.after(100, lambda: (dlg.grab_set(), dlg.focus_set()))

    for label, value in (('Show', 'show'), ('Hide', 'hide')):
        panels_menu.add_radiobutton(label=label, value=value, variable=panelsVar,
                                    command=onPanelToggle)

    # File > Parameters: save / load / reset the entry-box values of the Erase,
    # Program and Read panels (the only settings that are NOT saved automatically)
    params_menu = Menu(file_menu, tearoff=False)
    file_menu.insert_cascade(8, label="Parameters", menu=params_menu)
    file_menu.insert_separator(9)                    # before "Exit"

    def showStatus(msg, ms=3000):
        """Shows msg in the status bar for a few seconds"""
        old = stsBarComm.cget('text')
        stsBarComm.configure(text=msg)
        root.after(ms, lambda: stsBarComm.configure(text=old)
                   if stsBarComm.cget('text') == msg else None)

    def saveParams():
        serCom.saveConfig(params=True)
        showStatus('Parameters saved')

    def loadParams():
        serCom.loadConfig(prefs=False)
        showStatus('Parameters loaded')

    def defaultParams():
        serCom.loadDefaultParams()
        showStatus('Default parameters restored (File > Parameters > Save '
                   'to keep them)')

    # Scripts (File > Scripts). Both kinds run on the GUI thread and call
    # root.update() between commands, so the window stays alive and Esc is seen.
    #   Command script: a text file, one Terminal command per line
    #                   (see dubLibs/run_cmd_script.py)
    #   Python script : a Python file that uses the `dub` object
    #                   (see dubLibs/run_py_script.py)
    scriptStop = [False]

    def pickScript(title, filetypes):
        """Asks for a script file and remembers its folder; returns the path"""
        name = askopenfilename(
            title=title, initialdir=serCom.scriptDir or defaultScriptDir(),
            filetypes=filetypes)
        if name:
            serCom.scriptDir = os.path.dirname(name)      # start here next time
            serCom.saveConfig()
        return name

    def scriptReady():
        """True if a script may be started now"""
        if serCom.scriptRunning:
            return False
        if serCom.portStatus != 'connected':
            serCom.checkConnection()
            return False
        return True

    def runScript():
        """File > Scripts > Run Command Script"""
        if not scriptReady():
            return
        name = pickScript('Run Command Script', (
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
        serCom.scriptRunning = True
        scriptStop[0] = False
        term.scriptPrint(f'--- Running script {os.path.basename(name)} '
                         f'({len(commands)} commands) ---')
        reason = None
        try:
            for lineno, cmd in commands:
                if scriptStop[0]:
                    reason = 'stopped by the user'
                    break
                reply = term.runScriptCommand(cmd)
                root.update()
                if run_cmd_script.is_error(reply):
                    reason = f'error at line {lineno}: {cmd}'
                    break
        finally:
            serCom.scriptRunning = False
        term.scriptPrint('--- Script finished ---' if reason is None
                         else f'--- Script stopped: {reason} ---')

    def runPythonScript():
        """File > Scripts > Run Python Script"""
        if not scriptReady():
            return
        name = pickScript('Run Python Script', (
            ('Python scripts', '*.py'), ('All files', '*.*')))
        if not name:
            return
        executePython(name)

    def executePython(path):
        """Runs a Python file with the `dub` object and reports how it ended"""
        api = run_py_script.DubApi(
            term, du, root.update, lambda: scriptStop[0],
            ask=lambda prompt, default='': simpledialog.askstring(
                'Script', prompt, initialvalue=default, parent=root),
            confirm=lambda question: askyesno('Script', question, parent=root),
            notify=lambda text: showinfo('Script', text, parent=root))
        serCom.scriptRunning = True
        scriptStop[0] = False
        term.scriptPrint(f'--- Running Python script {os.path.basename(path)} ---')
        try:
            ok, message = run_py_script.run_file(path, api, term)
        finally:
            serCom.scriptRunning = False
        term.scriptPrint('--- Script finished ---' if ok
                         else f'--- Script stopped: {message} ---')

    def stopScript():
        scriptStop[0] = True

    # Tools menu: one entry for every script in the tools folder that has a
    # "# TOOL: name" header (see dubLibs/tools.py). Rebuilt each time it opens.
    def runTool(tool):
        if not scriptReady():
            return
        if tool['confirm'] and not askyesno(tool['name'], tool['confirm']):
            return
        if tool['description']:
            showStatus(tool['description'], 8000)
        executePython(tool['path'])

    def openToolsFolder():
        folder = toolsFolder()
        if os.path.isdir(folder):
            os.startfile(folder)
        else:
            showerror('Tools', f'The tools folder was not found:\n{folder}')

    def refreshTools():
        tools_menu.delete(0, 'end')
        found = tools.find_tools(toolsFolder())
        for tool in found:
            tools_menu.add_command(label=tool['name'],
                                   command=lambda t=tool: runTool(t))
        if not found:
            tools_menu.add_command(label='(no tools found)', state='disabled')
        tools_menu.add_separator()
        tools_menu.add_command(label='Open Tools Folder',
                               command=openToolsFolder)

    root.bind('<Escape>', lambda _e: stopScript())

    def openForProgramming():
        """File > Open Firmware File: pick a .bin, S-record or Intel HEX file and
        set the Program panel up for it ("Load from File" mode)"""
        if program.openFile():
            program.progModeVar.set('file')
            program.grayOutEntry()

    def programLoadedFile():
        """File > Program Loaded File: with the panels shown it asks for a
        confirmation (the Offset is the one in the Program panel); with the
        panels hidden the question also asks for the Offset."""
        image = program.image
        if image is None:
            showinfo('Program', 'No file is loaded.\nUse File > Open Firmware '
                     'File first.')
            return
        if not scriptReady():
            return
        if serCom.showPanels:
            try:
                offset = parseField('Offset', program.start_addr.get())
            except ValueError as e:
                showerror('Program', str(e))
                return
            text = (f'Program {program.imageName} ({image.describe()})?\n\n'
                    f'It will be written to:\n{program.rangesText(offset)}\n\n'
                    'Nothing is erased first.')
            if not askyesno('Program File', text, parent=root):
                return
        else:
            text = (f'Program {program.imageName} ({image.describe()}).\n\n'
                    f'Addresses in the file:\n{program.rangesText()}\n\n'
                    'Offset (hex) added to every address, normally 0.\n'
                    'Nothing is erased first. Click OK to program.')
            answer = simpledialog.askstring('Program File', text,
                                            initialvalue='0', parent=root)
            if answer is None:
                return
            try:
                offset = parseField('Offset', answer)
            except ValueError as e:
                showerror('Program', str(e))
                return
            program.start_addr.set(f'{offset:X}')
        program.progModeVar.set('file')
        program.grayOutEntry()
        program.program()

    def closeLoadedFile():
        """File > Close File: forget the loaded file"""
        program.closeFile()
        showStatus('File closed')

    def refreshFileMenu():
        """File menu opens: Program and Close need a loaded file; the grey
        line says which one is loaded"""
        image = program.image
        state = NORMAL if image is not None else DISABLED
        file_menu.entryconfigure(1, state=state)
        file_menu.entryconfigure(3, state=state)
        file_menu.entryconfigure(
            2, label=(f'Loaded: {program.imageName} ({image.size} bytes)'
                      if image is not None else 'No file loaded'))

    file_menu.configure(postcommand=refreshFileMenu)

    def fileShortcut(action):
        """Runs a menu action from a key; 'break' keeps the Terminal's own
        Ctrl+O / Ctrl+P (open line, previous line) from also running"""
        def handler(_event=None):
            action()
            return 'break'
        return handler

    root.bind('<Control-o>', fileShortcut(lambda: openForProgramming()))
    root.bind('<Control-p>', fileShortcut(lambda: programLoadedFile()))
    term.txt.bind('<Control-o>', fileShortcut(lambda: openForProgramming()))
    term.txt.bind('<Control-p>', fileShortcut(lambda: programLoadedFile()))

    def saveTerminalLog():
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
                fh.write(term.txt.get('1.0', 'end-1c') + '\n')
        except OSError as e:
            showerror('Save Terminal Log', f'Could not write the file:\n{e}')
            return
        showStatus('Terminal log saved')

    params_menu.add_command(label="Save", command=saveParams)
    params_menu.add_command(label="Load", command=loadParams)
    params_menu.add_command(label="Defaults", command=defaultParams)

    help_menu = Menu(my_menu, tearoff=False)
    my_menu.add_cascade(label="Help", menu=help_menu)
    help_menu.add_command(label="Help", accelerator="F1", command=showHelp)
    root.bind('<F1>', showHelp)
    help_menu.add_separator()
    help_menu.add_command(label="About", command=showAbout)

    # Help > Documents: one entry for every file in the docs folder
    # (see dubLibs/documents.py); rebuilt each time the submenu opens.
    docs_menu = Menu(help_menu, tearoff=False,
                     postcommand=lambda: refreshDocs())
    help_menu.insert_cascade(1, label="Documents", menu=docs_menu)
    help_menu.insert_command(2, label="Datasheet", command=lambda: openDatasheet())
    help_menu.insert_command(3, label="Datasheet Source...",
                             command=lambda: editDatasheetUrl())

    def openDocument(path):
        try:
            os.startfile(path)
        except OSError as e:
            showerror('Documents', f'Could not open the file:\n{path}\n\n{e}')

    def openDatasheet():
        """Help > Datasheet: the datasheet of the device in the status bar"""
        part = (datasheet.part_from_status(serCom.serParams)
                if serCom.portStatus == 'connected' else '')
        if not part:
            showinfo('Datasheet', 'No device is shown in the status bar.\n\n'
                     'Connect the board with a device in the socket first.')
            return
        # the docs folder, then %APPDATA%\Dubrovnik\Datasheets (also searched
        # in a "datasheets" subfolder of docs); no admin rights needed there
        local = datasheet.find_local(
            (docsFolder(), serCom.dubrovnikConfigPath), part)
        if local:
            openDocument(local)
            showStatus(f'Datasheet for {part}: {os.path.basename(local)}', 6000)
            return
        url = datasheet.build_url(serCom.datasheetUrl, part)
        try:
            webbrowser.open(url)
        except Exception as e:
            showerror('Datasheet', f'Could not open the browser:\n{url}\n\n{e}')
            return
        showStatus(f'Datasheet for {part}: opened {url}', 8000)

    def editDatasheetUrl():
        """Help > Datasheet Source...: where to look when there is no local file"""
        text = simpledialog.askstring(
            'Datasheet Source',
            'Web address used by Help > Datasheet when no datasheet file is in '
            'the docs folder.\n{part} is replaced by the part number of the '
            'device. An address without {part} is opened as it is.\n\n'
            'Clear the box to go back to the default (Renesas search).',
            initialvalue=serCom.datasheetUrl, parent=root)
        if text is None:            # Cancel
            return
        text = text.strip()
        url = datasheet.clean_url(text) if text else datasheet.DEFAULT_URL
        if text and url != text:
            showerror('Datasheet Source', 'The address must start with http:// '
                      'or https://')
            return
        serCom.datasheetUrl = url
        serCom.saveConfig()
        showStatus('Datasheet source saved', 4000)

    def openDocsFolder():
        folder = docsFolder()
        if os.path.isdir(folder):
            os.startfile(folder)
        else:
            showerror('Documents', f'The documents folder was not found:\n{folder}')

    def refreshDocs():
        docs_menu.delete(0, 'end')
        found = documents.find_documents(docsFolder())
        for label, path in found:
            docs_menu.add_command(label=label,
                                  command=lambda p=path: openDocument(p))
        if not found:
            docs_menu.add_command(label='(no documents found)', state='disabled')
        docs_menu.add_separator()
        docs_menu.add_command(label='Open Documents Folder',
                              command=openDocsFolder)

    serCom.loadConfig()  # includes autoConnect and lastUsedPort
    applyTerminal()
    syncPanels()   # before the window size is worked out below

    # Save the connection settings whenever they change, so they survive even
    # if the app is killed instead of closed normally. The entry-box values are
    # saved only by File > Parameters > Save.
    # (Traces are added after loadConfig so loading doesn't trigger a save.)
    serCom.chk_var.trace_add('write', lambda *_args: serCom.saveConfig())

    # * At this point we have a list of valid COM ports.
    # * Next step is to connect to one of them.
    if serCom.autoConnect and portList:  # auto connect, if a board was found
        if len(portList) > 1:  # no need to check if ==0. boardcom.py already does
            if serCom.lastUsedPort in portList:  # if last used port is in the portList
                # connect to that port
                serCom.connectPort(serCom.lastUsedPort,
                                   checkIsFlashPresent=False)
        else:
            # otherwise connect to the first in the list
            serCom.connectPort(portList[0], checkIsFlashPresent=False)
    # If not autoconnect then do not connect to anything

        # * At this point we are connected to the UART chip on Dubrovnik, but not yet
        # * to the MCU. It may require a manual RESET to boot.
        if serCom.portStatus == 'connected':   # the port could be opened
            resp = comm.connectToMCU()
            # print(resp)
            term.clear()

            if comm.isFlashPresent() == 0:
                showwarning(
                    'Warning', 'No flash device detected\nInstall a device and RESET the board')
            else:                   # show the device in the status bar
                try:
                    serCom.deviceDetected(du.get_part_number(comm))
                except Exception:
                    pass            # the status bar just shows no device

    elif serCom.autoConnect:     # Auto connect is on, but no board was found
        showwarning(
            'No board found',
            'No Dubrovnik board was found.\n\n1. Connect the USB cable\n'
            '2. Turn on the board\n3. Press the RESET button\n\n'
            'Then click Connect (the COM port list refreshes when you open it).')

    # Board commands (volt, freq, config, ...) don't need a flash device, so the
    # terminal must stay usable. The modal warning steals focus: give it back.
    root.focus_force()
    term.txt.focus_set()
    term.txt.mark_set(INSERT, END)

    stsBarComm.config(text=serCom.serParams)

    # Minimum width is the natural width of the panels row (serCom on top of
    # erase/program/read), so those three panels stay fully visible -- but
    # capped to the available screen size so the window still fits on small
    # monitors (e.g. 640x480). If the natural size doesn't fit, open the
    # window already shrunk to the screen.
    root.update_idletasks()
    reqW, reqH = root.winfo_reqwidth(), root.winfo_reqheight()
    scrW, scrH = root.winfo_screenwidth(), root.winfo_screenheight()
    marginW, marginH = 40, 80  # leave room for taskbar / window chrome
    fitW = min(reqW, scrW - marginW)
    fitH = min(reqH, scrH - marginH)
    if reqW > scrW - marginW or reqH > scrH - marginH:
        root.geometry(f'{fitW}x{fitH}+0+0')
    root.minsize(width=fitW, height=1)

    # Restore the window size saved at the last exit, if it fits on this
    # display; otherwise (or on first run) keep the default size.
    if serCom.winSize:
        savedW, savedH = serCom.winSize
        if savedW <= scrW - marginW and savedH <= scrH - marginH:
            geom = f'{max(savedW, fitW)}x{savedH}'
            if serCom.winPos:
                # only if the title bar is still reachable on a monitor
                # (a monitor may have been removed since the last run)
                x, y = serCom.winPos
                vx, vy = root.winfo_vrootx(), root.winfo_vrooty()
                vw, vh = root.winfo_vrootwidth(), root.winfo_vrootheight()
                if (vx - 100 < x < vx + vw - 100 and vy - 10 <= y < vy + vh - 60):
                    geom += f'+{x}+{y}'
            root.geometry(geom)

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

    def onClose():
        """Store the last used entry values and window size on exit."""
        if serCom.scriptRunning:          # stop a running script first
            stopScript()
            root.after(300, onClose)
            return
        try:
            if root.state() == 'normal':      # not minimized / maximized
                serCom.winSize = (root.winfo_width(), root.winfo_height())
                serCom.winPos = (root.winfo_x(), root.winfo_y())
            serCom.saveConfig()
        finally:
            root.destroy()

    root.protocol('WM_DELETE_WINDOW', onClose)

    mainloop()
