"""The remembered settings of the Workbench (no GUI code).

One Settings object is created at start-up and handed to whoever needs it. It
holds the values, knows their defaults, checks what it reads from the file and
writes the file. The file is %APPDATA%\\Dubrovnik\\dubrovnik_workbench.cfg and may
be edited by hand or damaged, so loading never raises: a bad value falls back to
its default (see cfgfile).

    settings = Settings()
    status, params = settings.load(choices={'readSpiMode': ('SPI', 'QPI')})
    settings.termFontSize = 16
    settings.save()

The entry-box values of the Erase, Program and Read panels are the "params"
(PARAM_KEYS). They are saved only when save() is given them (File > Parameters
> Save); otherwise the values already stored in the file are kept.
"""
import os

from dubLibs import cfgfile, datasheet, hexdump, termstyle

# Default value of every remembered setting (also the fallback for bad values)
DEFAULTS = dict(
    autoConnect=0, lastUsedPort='',
    eraseBlkSize='4', eraseStartAddr='0', eraseNumBlocks='1',
    progPattern='cafe0000', progIncrement='1', progStartAddr='0',
    progLength='100',
    readSpiMode='SPI', readStartAddr='0', readLength='100',
    appearance='system', terminalTheme='dark', showPanels=True,
    displayMode='Binary (b)', scriptFolder='', programFolder='',
    menuTextSize='normal',
    # Terminal look (View > Terminal...). terminalTheme is one of TERM_CHOICES;
    # the three colours are used by the 'custom' theme.
    terminalBg='#1B1F24', terminalFg='#D6DBE1', terminalSelect='#34506E',
    terminalFont='Consolas', terminalFontSize=15,
    datasheetUrl=datasheet.DEFAULT_URL,     # Help > Datasheet Source...
    # View > Hex Dump...: layout of the Read panel's Hex Dump display mode
    hexBytesPerRow=16, hexAscii=True, hexUpper=True, hexGap=True,
    # File > Scripts: show the listing of a command script before it runs, and print its comments
    showScriptListing=True, showScriptComments=True)

# The keys of the entry-box values of the Erase, Program and Read panels
PARAM_KEYS = ('eraseBlkSize', 'eraseStartAddr', 'eraseNumBlocks',
              'progPattern', 'progIncrement', 'progStartAddr', 'progLength',
              'readSpiMode', 'readStartAddr', 'readLength')

APPEARANCE_CHOICES = ('light', 'dark', 'system')
TERM_CHOICES = ('auto', 'light', 'dark', 'custom')   # 'auto' follows the window


class Settings:
    """Attributes (names as used by the program):
    autoConnect, lastUsedPort            connection panel
    appearance, showPanels, menuSize     window
    winSize (width, height) or None, winPos (x, y) or None
    termTheme, termBg, termFg, termSelect, termFont, termFontSize   Terminal
    hexRow, hexAscii, hexUpper, hexGap   Hex Dump layout
    scriptListing, scriptComments        command scripts: show the listing first, print the comments
    dispMode                             Read panel display mode
    scriptDir, programDir                last folders used
    datasheetUrl
    folder, cfgFile                      where the settings are kept"""

    def __init__(self, folder=None):
        d = DEFAULTS
        self.autoConnect = 0
        self.lastUsedPort = ''
        self.winSize = None
        self.winPos = None
        self.scriptDir = ''
        self.programDir = ''
        self.appearance = d['appearance']
        self.dispMode = d['displayMode']
        self.showPanels = d['showPanels']
        self.termTheme = d['terminalTheme']
        self.termBg = d['terminalBg']
        self.termFg = d['terminalFg']
        self.termSelect = d['terminalSelect']
        self.termFont = d['terminalFont']
        self.termFontSize = d['terminalFontSize']
        self.menuSize = d['menuTextSize']
        self.datasheetUrl = d['datasheetUrl']
        self.hexRow = d['hexBytesPerRow']
        self.hexAscii = d['hexAscii']
        self.hexUpper = d['hexUpper']
        self.hexGap = d['hexGap']
        self.scriptListing = d['showScriptListing']
        self.scriptComments = d['showScriptComments']

        # %AppData%\Dubrovnik is created if it does not exist
        self.folder = folder or os.path.join(os.getenv('APPDATA') or '', 'Dubrovnik')
        if not os.path.isdir(self.folder):
            os.mkdir(self.folder)
        self.cfgFile = os.path.join(self.folder, 'dubrovnik_workbench.cfg')
        self.migrateOldConfig()

    def hexOptions(self):
        """The Hex Dump layout as keyword arguments of the hexdump functions"""
        return dict(per_row=self.hexRow, show_ascii=self.hexAscii,
                    upper=self.hexUpper, gap=self.hexGap)

    def migrateOldConfig(self):
        """First run: start from the settings of the older app (dubrovnik.cfg,
        written by the discontinued Classic edition), without that app's own
        window-size entries."""
        oldFile = os.path.join(self.folder, 'dubrovnik.cfg')
        if os.path.isfile(self.cfgFile) or not os.path.isfile(oldFile):
            return
        cfg, status = cfgfile.read_json(oldFile)
        if status == 'ok':
            for key in ('mainWindowWidth', 'mainWindowHeight',
                        'mainWindowX', 'mainWindowY'):
                cfg.pop(key, None)
            cfgfile.write_json(self.cfgFile, cfg)

    def save(self, params=None):
        """Writes the settings file. params (a dict with the PARAM_KEYS) are
        written too; without them the values already stored in the file are
        kept, and so is everything else in it that this program does not know.
        Returns True on success."""
        cfg, _ = cfgfile.read_json(self.cfgFile)    # keeps the stored values
        cfg.update({'autoConnect': self.autoConnect,
                    'lastUsedPort': self.lastUsedPort,
                    'appearance': self.appearance,
                    'terminalTheme': self.termTheme,
                    'terminalBg': self.termBg,
                    'terminalFg': self.termFg,
                    'terminalSelect': self.termSelect,
                    'terminalFont': self.termFont,
                    'terminalFontSize': self.termFontSize,
                    'menuTextSize': self.menuSize,
                    'datasheetUrl': self.datasheetUrl,
                    'hexBytesPerRow': self.hexRow,
                    'hexAscii': self.hexAscii,
                    'hexUpper': self.hexUpper,
                    'hexGap': self.hexGap,
                    'showPanels': self.showPanels,
                    'showScriptListing': self.scriptListing,
                    'showScriptComments': self.scriptComments,
                    'displayMode': self.dispMode,
                    'scriptFolder': self.scriptDir,
                    'programFolder': self.programDir})
        if self.winSize:
            cfg['windowWidth'], cfg['windowHeight'] = self.winSize
        if self.winPos:
            cfg['windowX'], cfg['windowY'] = self.winPos
        if params:
            cfg.update(params)
        return cfgfile.write_json(self.cfgFile, cfg)

    def load(self, prefs=True, choices=None):
        """Reads the settings file. Returns (status, params).

        status 'ok': the file was read. With prefs=True the attributes are set
        from it (bad values become defaults); params is a dict of the stored
        entry-box values (PARAM_KEYS), for the caller to put into the panels.
        status 'defaults': there was no usable file (first run, or damaged and
        kept as .bad). autoConnect and lastUsedPort are reset, params is None;
        the caller sets the panels to their defaults and saves.

        choices: {key: allowed values} for the keys whose allowed values the
        caller knows (eraseBlkSize, readSpiMode, displayMode, menuTextSize)."""
        cfg, status = cfgfile.read_json(self.cfgFile)
        if status != 'ok':
            self.autoConnect = 0
            self.lastUsedPort = ''
            return 'defaults', None
        v = cfgfile.clean(cfg, DEFAULTS)
        allowed = {'appearance': APPEARANCE_CHOICES,
                   'terminalTheme': TERM_CHOICES}
        allowed.update(choices or {})
        for key, values in allowed.items():
            if v[key] not in values:
                v[key] = DEFAULTS[key]
        termstyle.repair(v, DEFAULTS)
        if v['hexBytesPerRow'] not in hexdump.ROW_SIZES:
            v['hexBytesPerRow'] = DEFAULTS['hexBytesPerRow']
        if prefs:
            self.autoConnect = v['autoConnect']
            self.lastUsedPort = v['lastUsedPort']
            self.appearance = v['appearance']
            self.termTheme = v['terminalTheme']
            self.termBg, self.termFg = v['terminalBg'], v['terminalFg']
            self.termSelect = v['terminalSelect']
            self.termFont = v['terminalFont']
            self.termFontSize = v['terminalFontSize']
            self.menuSize = v['menuTextSize']
            self.datasheetUrl = datasheet.clean_url(v['datasheetUrl'])
            self.hexRow, self.hexAscii = v['hexBytesPerRow'], v['hexAscii']
            self.hexUpper, self.hexGap = v['hexUpper'], v['hexGap']
            self.showPanels = v['showPanels']
            self.scriptListing = v['showScriptListing']
            self.scriptComments = v['showScriptComments']
            self.dispMode = v['displayMode']
            self.scriptDir = v['scriptFolder'] if os.path.isdir(v['scriptFolder']) else ''
            self.programDir = (v['programFolder']
                               if os.path.isdir(v['programFolder']) else '')
            self.winSize = cfgfile.int_pair(cfg, 'windowWidth', 'windowHeight',
                                            200, 20000)
            self.winPos = cfgfile.int_pair(cfg, 'windowX', 'windowY',
                                           -32000, 32000)
        return 'ok', {k: v[k] for k in PARAM_KEYS}
