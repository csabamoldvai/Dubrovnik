import datetime
import os
import pathlib
import sys
import tempfile
import traceback
import webbrowser
from tkinter import (
    DISABLED, END, EW, INSERT, NORMAL, NSEW, NW, BooleanVar, StringVar)
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
from dubLibs import assistant_config
from dubLibs import documents
from dubLibs import settings as settings_lib
from dubLibs.settings import Settings
from dubLibs import termstyle
from dubLibs.fields import parseField
from dubLibs.version import VERSION as APP_VERSION
from dubLibs import dubrovnik  # instead of "from dubLibs import Dubrovnik as du"
from dubGui import menus
from dubGui.dialogs import messages
from dubGui.dialogs.assistant_settings import AssistantSettingsDialog
from dubGui.dialogs.assistant_window import AssistantWindow, ScriptReview
from dubGui.dialogs.file_viewer import FileViewer
from dubGui.dialogs.hex_dialog import HexDialog
from dubGui.dialogs.script_preview import ScriptPreview
from dubGui.dialogs.terminal_dialog import TerminalDialog
from dubGui.look import TERM_THEMES, styleCombobox, styleMenus
from dubGui.panels.erase_panel import EraseFrame
from dubGui.panels.program_panel import ProgramFrame
from dubGui.panels.read_panel import ReadFrame
from dubGui.panels.serial_panel import SerComFrame
from dubGui.panels.terminal import Terminal


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


class App:
    """The Dubrovnik Workbench: builds the window, the panels and the menus, and
    holds what they share (the settings panel serCom, the Terminal, the board
    library object). The menu actions and dialogs are its methods."""

    def __init__(self):
        self.root = ctk.CTk()
        self.root.title(f'Dubrovnik Workbench {APP_VERSION}')
        self.root.report_callback_exception = self.onCallbackError

        comm = boardcom.BoardComm()   # create an instance of class Comm
        self.du = dubrovnik.Dubrovnik()
        self.settings = Settings()
        self.scriptStop = [False]      # set by Esc or a lost connection: stops scripts and programming

        self.buildStatusBar()
        portList = self.buildPanels(comm)
        self.buildMenus()
        self.bindKeys()
        self.initState()
        self.loadAndSync()
        self.startupNote = None      # (Terminal text, status bar text) of a start-up problem
        self.autoConnect(comm, portList)
        self.focusTerminal()
        self.placeWindow()
        self.showStartupNote()

    def buildStatusBar(self):
        """The status bar at the bottom of the window"""
        # ***************************
        # ****** Status Bar *********
        # ***************************
        self.stsBarComm = ctk.CTkLabel(self.root, text='Not connected', anchor='w')
        self.stsBarComm.grid(row=5, column=0, padx=10, pady=4,
                        columnspan=4, sticky=EW)


    def buildPanels(self, comm):
        """The Terminal, the connection panel and the three panels; returns the list of COM ports found"""
        # the menu font is also used by the Terminal's pop-up menu
        self.scale = ScalingTracker.get_widget_scaling(self.root)
        self.menuFamily = ctk.ThemeManager.theme['CTkFont']['family']
        self.menuFont = (self.menuFamily, -round(MENU_SIZES[self.settings.menuSize] * self.scale))

        # ***********************************
        # ******** Terminal Window **********
        # ***********************************
        self.term = Terminal(self.root, self.du, self.menuFont)
        self.term.grid(row=3, column=0, padx=10, pady=4, columnspan=4, sticky=NSEW)
        self.term.grid_columnconfigure(0, weight=1)
        self.term.grid_rowconfigure(1, weight=1)  # txt widget lives at row 1
        self.term.comm = comm

        portList = comm.findPorts(exit_if_none=False)   # may be empty: no board yet

        # *******************************************
        # ****** Serial Communications Panel ********
        # *******************************************
        self.serCom = SerComFrame(self.root, self.settings, self.du, self.term, self.stsBarComm,
                                self.scriptStop, DEBUG=False)
        self.serCom.grid(row=1, column=0, padx=(10, 3), pady=(8, 4), sticky=NSEW)
        if portList:
            self.serCom.combo.set(portList[0])
        self.serCom.comm = comm
        self.term.serCom = self.serCom
        self.serCom.checkLink()      # notices when the board is switched off

        # ******************************
        # ****** Erase Panel   *********
        # ******************************
        # The three panels sit in one row container so that hidden panels collapse
        # and the remaining ones close up (see layoutPanels below).
        self.panelRow = ctk.CTkFrame(self.root, fg_color='transparent', corner_radius=0)
        self.panelRow.grid(row=2, column=0, columnspan=4, sticky=NW)
        self.erase = EraseFrame(self.panelRow, self.serCom, self.term, self.du, DEBUG=False)
        self.erase.comm = comm

        # ******************************
        # ****** Program Panel *********
        # ******************************
        # TODO rename program to progFrm
        self.program = ProgramFrame(self.panelRow, self.serCom, self.term, self.du, self.settings,
                                    self.scriptStop, self.showStatus, DEBUG=False)
        self.program.comm = comm

        # ***************************
        # ****** Read Panel *********
        # ***************************
        self.read = ReadFrame(self.panelRow, self.serCom, self.term, self.du, self.settings, DEBUG=False)
        self.read.comm = comm

        # Let the terminal row absorb all extra vertical space, and let the three
        # panel columns share extra horizontal space evenly.
        self.root.grid_rowconfigure(3, weight=1)
        # Panels keep their natural width; only the spacer column 3 absorbs extra
        # horizontal space, so widening the window doesn't stretch the panels.
        for col in (0, 1, 2):
            self.root.grid_columnconfigure(col, weight=0)
        self.root.grid_columnconfigure(3, weight=1)
        return portList

    def buildMenus(self):
        """The menu bar and the menus, from the tables of dubGui/menus.py"""
        # ############ MENU
        # A native Windows menu bar ignores font settings, so build the bar from
        # CTk buttons (row 0) that pop up regular menus, whose font can be set.
        # The menus are described by the tables in dubGui/menus.py.
        self.menuButtons = []     # (button, font, label) of the menu bar, see applyMenuSize
        self.menuBar = ctk.CTkFrame(self.root, corner_radius=0, height=30)
        self.menuBar.grid(row=0, column=0, columnspan=4, sticky=EW)

        # the Tk variables behind the radio items of the View menu
        self.appearanceVar = StringVar(value=self.settings.appearance)
        self.menuSizeVar = StringVar(value=self.settings.menuSize)
        self.scriptListingVar = BooleanVar(value=self.settings.scriptListing)
        self.scriptCommentsVar = BooleanVar(value=self.settings.scriptComments)

        bar = menus.MenuBar(self.menuBar, self.menuButtons, self.settings, MENU_SIZES)
        self.allMenus = []        # every Tk menu, to restyle and resize them together
        self.menus = {}           # key -> menus.BuiltMenu, to find an item by its key
        for spec in menus.MENUS:
            built = menus.build(self.root, spec.items, self, self.menuFont,
                                self.allMenus, spec.postcommand)
            bar.add(spec.label, built.menu)
            self.menus[spec.key] = built
        # the Tk menus that other code (and the tests) use
        self.file_menu = self.menus['file'].menu
        self.firmware_menu = self.menus['file'].sub('firmware').menu
        self.tools_menu = self.menus['tools'].menu
        self.view_menu = self.menus['view'].menu
        self.docs_menu = self.menus['help'].sub('documents').menu


    def bindKeys(self):
        """Keyboard shortcuts of the main window"""
        # Scripts (File > Scripts). Both kinds run on the GUI thread and call
        # root.update() between commands, so the window stays alive and Esc is seen.
        #   Command script: a text file, one Terminal command per line
        #                   (see dubLibs/run_cmd_script.py)
        #   Python script : a Python file that uses the `dub` object
        #                   (see dubLibs/run_py_script.py)
        self.root.bind('<Escape>', lambda _e: self.stopScript())

        self.root.bind('<Control-o>', self.fileShortcut(lambda: self.openForProgramming()))
        self.root.bind('<Control-p>', self.fileShortcut(lambda: self.programLoadedFile()))
        self.term.txt.bind('<Control-o>', self.fileShortcut(lambda: self.openForProgramming()))
        self.term.txt.bind('<Control-p>', self.fileShortcut(lambda: self.programLoadedFile()))
        self.term.onZoom = self.zoomTerminal
        self.root.bind('<F1>', showHelp)


    def initState(self):
        """The handles of the windows opened later and other state of the App"""
        self.zoomState = dict(save=None, restore=None, old=None)
        self.fileViewer = None
        self.hexDialog = None
        self.fontCache = []
        self.termDialog = None
        self.scriptPreview = None
        self.assistant = None             # dubLibs.assistant.Assistant, made when first needed
        self.assistantWindow = None
        self.assistantCfg = None          # the saved credentials, read when first needed
        self.assistantSettings = None


    def loadAndSync(self):
        """Loads the settings into the panels and the menus"""
        self.loadSettings()  # includes autoConnect and lastUsedPort
        self.menuSizeVar.set(self.settings.menuSize)
        self.scriptListingVar.set(self.settings.scriptListing)
        self.scriptCommentsVar.set(self.settings.scriptComments)
        self.applyMenuSize()          # the size just loaded from the settings file
        self.syncTheme()
        self.watchSystemAppearance()
        self.syncPanels()

        # Save the connection settings whenever they change, so they survive even
        # if the app is killed instead of closed normally. The entry-box values are
        # saved only by File > Parameters > Save.
        # (Traces are added after loadSettings so loading doesn't trigger a save.)
        self.serCom.chk_var.trace_add('write', self.serCom.autoConnectChanged)


    def autoConnect(self, comm, portList):
        """Connects to the board at start-up if the settings ask for it"""
        # * At this point we have a list of valid COM ports.
        # * Next step is to connect to one of them.
        if self.settings.autoConnect and portList:  # auto connect, if a board was found
            comm.retryDialog = False        # no Retry/Cancel pop-ups before the window is up
            try:
                if len(portList) > 1:  # no need to check if ==0. boardcom.py already does
                    if self.settings.lastUsedPort in portList:  # if last used port is in the portList
                        # connect to that port
                        self.serCom.connectPort(self.settings.lastUsedPort,
                                           checkIsFlashPresent=False)
                else:
                    # otherwise connect to the first in the list
                    self.serCom.connectPort(portList[0], checkIsFlashPresent=False)
                # If not autoconnect then do not connect to anything

                # * At this point we are connected to the UART chip on Dubrovnik, but not yet
                # * to the MCU. It may require a manual RESET to boot.
                if self.serCom.portStatus == 'connected':   # the port could be opened
                    self.probeBoard(comm)
                elif self.serCom.combo.get():               # it could not (in use?)
                    port = self.serCom.combo.get()
                    self.startupNote = (f'Could not open {port}. Make sure it is not used by '
                                        'another program, then click Connect.',
                                        f'Could not open {port}')
            finally:
                comm.retryDialog = True

        elif self.settings.autoConnect:     # Auto connect is on, but no board was found
            # no pop-up: the window must come up anyway. The note is shown once it is there.
            self.startupNote = ('No Dubrovnik board was found. 1. Connect the USB cable '
                                '2. Turn on the board 3. Press the RESET button. Then click '
                                'Connect (the COM port list refreshes when you open it).',
                                'No COM port found: connect the USB cable, turn on the board '
                                'and press RESET')

    def probeBoard(self, comm):
        """Start-up: talks to the MCU on the port that was just opened. A board that does
        not answer (switched off, not reset yet) must not keep the window from coming up:
        comm.retryDialog is off meanwhile (see autoConnect), so a timeout ends up here
        instead of in a Retry/Cancel loop that quits the program."""
        try:
            comm.connectToMCU()
            self.term.clear()
            if comm.isFlashPresent() == 0:
                self.serCom.deviceDetected('', failed=True)
                showwarning(
                    'Warning', 'No flash device detected\nInstall a device and RESET the board')
            else:                   # show the device in the status bar
                try:
                    self.serCom.deviceDetected(self.du.get_part_number(comm))
                except Exception:
                    pass            # the status bar just shows no device
        except boardcom.BoardTimeout:
            self.term.clear()
            self.startupNote = (f'Connected to {self.serCom.selPort}, but the board did not '
                                'answer. Press the RESET button (its start-up message then '
                                'appears here), verify that a valid SD card is inserted, or '
                                'verify that the MCU is functional.', '')
            self.serCom.markSilent()

    def onCallbackError(self, exc, val, tb):
        """Tk calls this for an error in a button, menu or timer callback. A board that does
        not answer (the user chose Cancel in the Retry/Cancel box) is not a bug: say so in
        the Terminal and the status bar and carry on. Anything else is printed as usual."""
        if isinstance(val, boardcom.BoardTimeout):
            self.term.displayText('*** ' + str(val) + ' ***')
            self.serCom.markSilent()
        else:
            traceback.print_exception(exc, val, tb)

    def showStartupNote(self):
        """A start-up problem is reported in the Terminal (and in the status bar, if it
        has something to say), not in a dialog that would hold the window back"""
        if self.startupNote:
            text, status = self.startupNote
            self.term.displayText('*** ' + text + ' ***')
            if status:
                self.stsBarComm.configure(text=status)
            self.startupNote = None


    def focusTerminal(self):
        """Gives the keyboard focus to the Terminal"""
        # Board commands (volt, freq, config, ...) don't need a flash device, so the
        # terminal must stay usable. The modal warning steals focus: give it back.
        self.root.focus_force()
        self.term.txt.focus_set()
        self.term.txt.mark_set(INSERT, END)

        self.stsBarComm.configure(text=self.serCom.serParams)


    def placeWindow(self):
        """Sets the size and the position of the window: minimum, saved or default"""
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
        if self.settings.winSize:
            savedW, savedH = self.settings.winSize
            if (savedW <= (self.scrW - self.marginW) / self.scale
                    and savedH <= (self.scrH - self.marginH) / self.scale):
                winW, winH = max(int(savedW), minW), max(int(savedH), minH)
        geom = f'{winW}x{winH}'
        if self.settings.winPos:
            # restore the position only if the window's title bar would still be
            # reachable on one of the monitors (a monitor may have been removed)
            x, y = self.settings.winPos
            if (vx - 100 < x < vx + vw - 100 and vy - 10 <= y < vy + vh - 60):
                geom += f'+{x}+{y}'
        self.root.geometry(geom)

        self.root.protocol('WM_DELETE_WINDOW', self.onClose)


    def run(self):
        """Shows the window and handles events until it is closed"""
        self.root.mainloop()


    def layoutPanels(self):
        """Shows or hides the three panels together (settings.showPanels). Shown
        panels sit side by side from the left, with 10 px outer margins and
        3 px between neighbours."""
        if not self.settings.showPanels:
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
        """Text of the Hide / Show Panels item of the View menu: the action it will do"""
        return ('Hide Panels (Erase/Program/Read)' if self.settings.showPanels
                else 'Show Panels (Erase/Program/Read)')

    def syncPanels(self):
        """Applies settings.showPanels to the menu text and the layout"""
        self.menus['view'].configure('panels', label=self.panelsLabel())
        self.layoutPanels()

    def onPanelToggle(self):
        """The Hide / Show Panels item was clicked: show or hide the panels, then
        change the window height by the height gained or lost so the Terminal
        keeps its size"""
        self.settings.showPanels = not self.settings.showPanels
        self.menus['view'].configure('panels', label=self.panelsLabel())
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
        self.settings.save()

    def showHelp(self, _event=None):
        """Help > Help (F1): open the user guide in the default web browser"""
        showHelp(_event)

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

    def loadDefaultParams(self):
        """Resets the entry boxes of the Erase, Program and Read panels"""
        self.erase.blockSize.set(self.erase.blockSizes[0])
        self.erase.startAddr.set('0')
        self.erase.numBlocks.set('1')
        self.program.pattern.set('cafe0000')
        self.program.increment.set('1')
        self.program.start_addr.set('0')
        self.program.length.set('100')
        self.read.spiMode.set(self.read.spiModes[0])
        self.read.startAddr.set('0')
        self.read.readLength.set('100')

    def paramValues(self):
        """The entry-box values of the Erase, Program and Read panels, in the
        form the settings file keeps them"""
        return {'eraseBlkSize': str(self.erase.blockSize.get()),
                'eraseStartAddr': str(self.erase.startAddr.get()),
                'eraseNumBlocks': str(self.erase.numBlocks.get()),
                'progPattern': self.program.pattern.get(),
                'progIncrement': self.program.increment.get(),
                'progStartAddr': self.program.start_addr.get(),
                'progLength': self.program.length.get(),
                'readSpiMode': self.read.spiMode.get(),
                'readStartAddr': self.read.startAddr.get(),
                'readLength': self.read.readLength.get()}

    def setParams(self, v):
        """Puts stored entry-box values (see paramValues) into the panels"""
        self.erase.blockSize.set(v['eraseBlkSize'])
        self.erase.startAddr.set(v['eraseStartAddr'])
        self.erase.numBlocks.set(v['eraseNumBlocks'])
        self.program.pattern.set(v['progPattern'])
        self.program.increment.set(v['progIncrement'])
        self.program.start_addr.set(v['progStartAddr'])
        self.program.length.set(v['progLength'])
        self.read.spiMode.set(v['readSpiMode'])
        self.read.startAddr.set(v['readStartAddr'])
        self.read.readLength.set(v['readLength'])

    def loadSettings(self, prefs=True, params=True):
        """Loads the settings file: the remembered settings (prefs) and/or the
        stored entry-box values (params) into the panels. A missing or damaged
        file, or a bad value in it, falls back to defaults; this never stops
        the app."""
        status, stored = self.settings.load(prefs=prefs, choices=dict(
            eraseBlkSize=self.erase.blockSizes,
            readSpiMode=self.read.spiModes,
            displayMode=tuple(self.read.dispmodeOptions),
            menuTextSize=tuple(MENU_SIZES)))
        if status == 'defaults':     # first run, or unreadable (kept as .bad)
            self.serCom.chk_var.set(0)
            self.loadDefaultParams()
            self.settings.save(self.paramValues())
            return
        if prefs:
            self.serCom.chk_var.set(self.settings.autoConnect)
            self.read.applyDispMode(self.settings.dispMode)
        if params:
            self.setParams(stored)

    def saveParams(self):
        self.settings.save(self.paramValues())
        self.showStatus('Parameters saved')

    def loadParams(self):
        self.loadSettings(prefs=False)
        self.showStatus('Parameters loaded')

    def defaultParams(self):
        self.loadDefaultParams()
        self.showStatus('Default parameters restored (File > Parameters > Save '
                   'to keep them)')

    def pickScript(self, title, filetypes):
        """Asks for a script file and remembers its folder; returns the path"""
        name = askopenfilename(
            title=title, initialdir=self.settings.scriptDir or defaultScriptDir(),
            filetypes=filetypes)
        if name:
            self.settings.scriptDir = os.path.dirname(name)      # start here next time
            self.settings.save()
        return name

    def scriptReady(self):
        """True if a script may be started now"""
        if self.serCom.scriptRunning:
            return False
        if self.serCom.portStatus != 'connected':
            self.serCom.checkConnection()
            return False
        return True

    def setScriptOptions(self):
        """File > Scripts > Show Script Listing / Comments: remember the choice"""
        self.settings.scriptListing = self.scriptListingVar.get()
        self.settings.scriptComments = self.scriptCommentsVar.get()
        self.settings.save()

    def runScript(self):
        """File > Scripts > Run Command Script"""
        if not self.scriptReady():
            return
        name = self.pickScript('Run Command Script', (
            ('Script files', '*.txt *.scr'), ('All files', '*.*')))
        if name:
            self.runCommandFile(name)

    def runCommandFile(self, name):
        """Reads a command script, shows its listing (if wanted) and runs it"""
        try:
            with open(name, encoding='utf-8-sig') as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError) as e:
            showerror('Run Command Script', f'Could not read the file:\n{e}')
            return
        lines = run_cmd_script.parse_lines(text)
        if not any(line[1] for line in lines):
            showinfo('Run Command Script', 'The file contains no commands.')
            return
        if not self.settings.scriptListing:
            self.runCommandLines(name, lines)
            return
        # the script runs only when the user chooses Run in the listing
        self.scriptPreview = ScriptPreview(
            self.root, os.path.basename(name), text, self.termColors(),
            self.settings.termFont, self.settings.termFontSize,
            lambda: self.runCommandLines(name, lines))

    def runCommandLines(self, name, lines):
        """Runs the commands of a parsed command script (see run_cmd_script.parse_lines)
        and prints its comments"""
        if not self.scriptReady():
            return
        commands = [line for line in lines if line[1]]
        self.serCom.scriptRunning = True
        self.scriptStop[0] = False
        self.term.scriptPrint(f'--- Running script {os.path.basename(name)} '
                         f'({len(commands)} commands) ---')
        reason = None
        try:
            for lineno, cmd, comment in lines:
                if self.scriptStop[0]:
                    reason = 'stopped by the user'
                    break
                if not self.settings.scriptComments:
                    comment = ''
                if not cmd:                 # a comment on its own line
                    if comment:
                        self.term.scriptPrint(f'# {comment}')
                    continue
                reply = self.term.runScriptCommand(cmd, comment)
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
                per_row=self.settings.hexRow, show_ascii=self.settings.hexAscii,
                upper=self.settings.hexUpper, gap=self.settings.hexGap))
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
    # "# TOOL: name" header, Python and command scripts (see dubLibs/tools.py).
    # Rebuilt each time it opens.
    def runTool(self, tool):
        if not self.scriptReady():
            return
        if tool['kind'] == 'command':
            self.runCommandFile(tool['path'])
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
        for i, tool in enumerate(found):
            if i and tool['kind'] != found[i - 1]['kind']:
                self.tools_menu.add_separator()     # Python tools, then command scripts
            self.tools_menu.add_command(label=tool['name'],
                                   command=lambda t=tool: self.runTool(t))
        if not found:
            self.tools_menu.add_command(label='(no tools found)', state='disabled')
        self.tools_menu.add_separator()
        self.tools_menu.add_command(label='Open Tools Folder',
                               command=self.openToolsFolder)

    def openForProgramming(self):
        """File > Image Files > Open File: pick a .bin, S-record or Intel HEX file and
        set the Program panel up for it ("Load from File" mode)"""
        if self.program.openFile():
            self.program.progModeVar.set('file')
            self.program.grayOutEntry()

    def programLoadedFile(self):
        """File > Image Files > Program Loaded File: with the panels shown it asks for a
        confirmation (the Offset is the one in the Program panel); with the
        panels hidden the question also asks for the Offset."""
        image = self.program.image
        if image is None:
            showinfo('Program', 'No file is loaded.\nUse File > Image Files > Open File '
                     'first.')
            return
        if not self.scriptReady():
            return
        if self.settings.showPanels:
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
        """File > Image Files > Close File: forget the loaded file"""
        self.program.closeFile()
        self.showStatus('File closed')

    def refreshFileMenu(self):
        """Image Files menu opens: Program and Close need a loaded file; the grey
        line says which one is loaded"""
        image = self.program.image
        state = NORMAL if image is not None else DISABLED
        firmware = self.menus['file'].sub('firmware')
        for key in ('view_file', 'program', 'close_file'):
            firmware.configure(key, state=state)
        firmware.configure(
            'loaded', label=(f'Loaded: {self.program.imageName} ({image.size} bytes)'
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
        """Applies settings.menuSize to the menu bar and all pop-up menus"""
        size = MENU_SIZES[self.settings.menuSize]
        self.menuFont = (self.menuFamily, -round(size * self.scale))
        for btn, font, label in self.menuButtons:
            font.configure(size=size)
            btn.configure(width=font.measure(label) + 20)
        for m in self.allMenus:
            m.configure(font=self.menuFont)

    def setMenuSize(self):
        self.settings.menuSize = self.menuSizeVar.get()
        self.applyMenuSize()
        self.settings.save()

    def applyAppearance(self):
        ctk.set_appearance_mode(self.settings.appearance)
        styleCombobox(self.root)
        styleMenus(self.allMenus)
        self.applyTerminal()            # the 'auto' Terminal theme follows the window

    def watchSystemAppearance(self, lastMode=[None]):
        """In 'System' mode Windows can switch light/dark while the app runs;
        re-apply the appearance rules when that happens."""
        mode = ctk.get_appearance_mode()
        if lastMode[0] not in (None, mode) and self.settings.appearance == 'system':
            self.applyAppearance()
            self.settings.save()
        lastMode[0] = mode
        self.root.after(2000, self.watchSystemAppearance)

    def setAppearance(self):
        self.settings.appearance = self.appearanceVar.get()
        self.applyAppearance()
        self.settings.save()

    def syncTheme(self):
        """Applies settings.appearance and the Terminal look (e.g. just loaded
        from the settings file)"""
        self.appearanceVar.set(self.settings.appearance)
        self.applyAppearance()

    # ---- Terminal look: View > Terminal... and Ctrl + mouse wheel ----------
    def termColors(self):
        """The Terminal colours (bg, fg, select) of the chosen theme"""
        theme = self.settings.termTheme
        if theme == 'auto':
            theme = 'dark' if ctk.get_appearance_mode() == 'Dark' else 'light'
        if theme == 'custom':
            return dict(bg=self.settings.termBg, fg=self.settings.termFg,
                        select=self.settings.termSelect)
        return TERM_THEMES[theme]

    def applyTerminal(self):
        self.term.applyColors(self.termColors())
        self.term.setFont(self.settings.termFont, self.settings.termFontSize)

    def zoomTerminal(self, step):
        """Ctrl + mouse wheel: bigger or smaller Terminal text. The setting is
        saved shortly after the wheel stops."""
        size = min(max(self.settings.termFontSize + step, TERM_SIZE_MIN), TERM_SIZE_MAX)
        if size != self.settings.termFontSize:
            self.settings.termFontSize = size
            self.applyTerminal()
            if self.zoomState['save']:
                self.root.after_cancel(self.zoomState['save'])
            self.zoomState['save'] = self.root.after(600, self.settings.save)
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
        """File > Image Files > View File: the whole loaded file as a hex dump, at
        the addresses it will be written to (file address + Offset)"""
        image = self.program.image
        if image is None:
            showinfo('View File', 'No file is loaded.\nUse File > Image Files > '
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
            self.settings.termFont, self.settings.termFontSize,
            self.settings.hexOptions())

    def showHexDialog(self):
        """View > Hex View...: layout of the Hex View display mode of the Read
        panel, with a sample. Nothing changes until OK."""
        if self.hexDialog is not None and self.hexDialog.win.winfo_exists():
            self.hexDialog.win.focus_set()
            return
        self.hexDialog = HexDialog(self.root, self.settings, self.termColors,
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
            self.root, self.settings, self.termColors, self.applyTerminal,
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

    def assistantConfig(self):
        """The credentials saved in Help > Assistant Settings"""
        if self.assistantCfg is None:
            self.assistantCfg = assistant_config.load(self.settings.folder)
        return self.assistantCfg

    def showAssistantSettings(self):
        win = self.assistantSettings
        if win is not None and win.win.winfo_exists():
            win.win.deiconify()
            win.win.focus_set()
            return
        self.assistantSettings = AssistantSettingsDialog(
            self.root, self.assistantConfig(), self.saveAssistantConfig)

    def saveAssistantConfig(self, config):
        if not assistant_config.save(self.settings.folder, config):
            showerror('Assistant Settings', 'Could not save the settings.')
            return
        self.assistantCfg = assistant_config.load(self.settings.folder)
        if self.assistant is not None:
            self.assistant.configure(self.assistantCfg)
        self.showStatus('Assistant settings saved')

    def showAssistant(self):
        win = self.assistantWindow
        if win is not None and win.win.winfo_exists():
            win.win.deiconify()
            win.win.focus_set()
            return
        from dubLibs import assistant
        if self.assistant is None:
            self.assistant = assistant.Assistant(helpFilePath(), toolsFolder(),
                                                 self.assistantConfig())
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
            (docsFolder(), self.settings.folder), part)
        if local:
            self.openDocument(local)
            self.showStatus(f'Datasheet for {part}: {os.path.basename(local)}', 6000)
            return
        url = datasheet.build_url(self.settings.datasheetUrl, part)
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
            [('OK', None), ('Cancel', False)], self.settings.datasheetUrl)
        if text is False:           # Cancel
            return
        text = (text or '').strip()
        url = datasheet.clean_url(text) if text else datasheet.DEFAULT_URL
        if text and url != text:
            showerror('Datasheet Source', 'The address must start with http:// '
                      'or https://')
            return
        self.settings.datasheetUrl = url
        self.settings.save()
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

    def onClose(self):
        """Store the last used entry values and window size on exit."""
        if self.serCom.scriptRunning:          # stop a running script first
            self.stopScript()
            self.root.after(300, self.onClose)
            return
        try:
            if self.root.state() == 'normal':      # not minimized / maximized
                self.settings.winSize = (round(self.root.winfo_width() / self.scale),
                                  round(self.root.winfo_height() / self.scale))
                self.settings.winPos = (self.root.winfo_x(), self.root.winfo_y())
            self.settings.save()
        finally:
            self.root.destroy()


def main():
    App().run()


if __name__ == "__main__":
    main()
