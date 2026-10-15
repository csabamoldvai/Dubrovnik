"""The menus of the Workbench as data.

Each menu is a list of items (see MENUS at the end). build() makes the Tk menu from such a
list, and the result finds an item by its key, so no code has to know that an item is "number
5": adding an item to a table moves nothing else.

    built = build(root, FILE, app, font, all_menus)      # a BuiltMenu
    built.configure('close_file', state=DISABLED)         # instead of entryconfigure(4, ...)
    built.sub('firmware').menu                            # the Tk menu of a submenu

A command is the name of an App method (looked up when the item is clicked, so a method that
is replaced later is the one that runs) or a function. The Tools and Documents menus are
emptied and filled again every time they open (their postcommand); their tables are empty.
"""
from dataclasses import dataclass, field
from tkinter import DISABLED, Menu
import customtkinter as ctk
from dubGui.look import PAL


@dataclass
class Item:
    """A command. command: name of an App method, or a function. when(app): the item is only
    there if this returns true (decided when the menu is built)."""
    key: str
    label: str
    command: object = None
    accelerator: str = None
    state: str = None
    when: object = None


@dataclass
class Radio:
    """A radio button. variable: name of the App attribute that holds the Tk variable."""
    key: str
    label: str
    value: str
    variable: str
    command: object = None


@dataclass
class Check:
    """A check button. variable: name of the App attribute that holds the Tk variable."""
    key: str
    label: str
    variable: str
    command: object = None


@dataclass
class Separator:
    key: str = None


@dataclass
class Submenu:
    """A cascade (or, in MENUS, a menu of the menu bar). postcommand: name of an App method
    that Tk calls just before the menu opens."""
    key: str
    label: str
    items: list = field(default_factory=list)
    postcommand: str = None


class BuiltMenu:
    """A Tk menu made by build(): menu is the Tk Menu; items are found by key."""

    def __init__(self, menu):
        self.menu = menu
        self._index = {}          # key -> position
        self._children = {}       # key -> BuiltMenu of a submenu

    def index(self, key):
        return self._index[key]

    def configure(self, key, **options):
        """entryconfigure of the item with this key"""
        self.menu.entryconfigure(self._index[key], **options)

    def sub(self, key):
        return self._children[key]


def _call(app, command):
    """A function Tk can call: the App method of that name (looked up at the click) or the function"""
    if command is None:
        return None
    if callable(command):
        return command
    return lambda: getattr(app, command)()


def build(parent, items, app, font, all_menus, postcommand=None):
    """Makes a Tk menu in parent from a list of items. Every Tk menu made (this one and its
    submenus) is also appended to all_menus, which the program restyles and resizes."""
    menu = Menu(parent, tearoff=False, font=font,
                **({'postcommand': _call(app, postcommand)} if postcommand else {}))
    all_menus.append(menu)
    built = BuiltMenu(menu)
    for item in items:
        if isinstance(item, Separator):
            menu.add_separator()
        elif isinstance(item, Submenu):
            child = build(menu, item.items, app, font, all_menus, item.postcommand)
            menu.add_cascade(label=item.label, menu=child.menu)
            built._children[item.key] = child
        elif isinstance(item, Check):
            menu.add_checkbutton(label=item.label, variable=getattr(app, item.variable),
                                 command=_call(app, item.command))
        elif isinstance(item, Radio):
            menu.add_radiobutton(label=item.label, value=item.value,
                                 variable=getattr(app, item.variable),
                                 command=_call(app, item.command))
        else:
            if item.when is not None and not item.when(app):
                continue
            options = {}
            if item.accelerator:
                options['accelerator'] = item.accelerator
            if item.state:
                options['state'] = item.state
            menu.add_command(label=item.label, command=_call(app, item.command), **options)
        if item.key:
            built._index[item.key] = menu.index('end')
    return built


class MenuBar:
    """Stand-in for the menu bar: a native Windows menu bar ignores font settings, so the
    bar is made of CTk buttons that pop up regular menus, whose font can be set.
    add(label, menu) adds a button that pops the menu up just below itself.
    buttons collects (button, font, label) so the text size can be changed later."""

    def __init__(self, frame, buttons, settings, sizes):
        self.frame, self.buttons, self.settings, self.sizes = frame, buttons, settings, sizes
        self.col = 0

    def add(self, label, menu):
        def popup():
            try:
                menu.tk_popup(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height())
            finally:
                menu.grab_release()
        font = ctk.CTkFont(size=self.sizes[self.settings.menuSize])
        btn = ctk.CTkButton(
            self.frame, text=label, width=font.measure(label) + 20, height=26,
            corner_radius=4, fg_color='transparent',
            hover_color=PAL['hover'], text_color=PAL['text'],
            font=font, command=popup)
        btn.grid(row=0, column=self.col, padx=(4 if self.col == 0 else 0, 0), pady=2)
        self.buttons.append((btn, font, label))
        self.col += 1


# ---- the tables --------------------------------------------------------------------------

FILE = [
    # File > Firmware: open a firmware file and program it (like Scripts below)
    Submenu('firmware', 'Firmware', [
        Item('open_file', 'Open File...', 'openForProgramming', accelerator='Ctrl+O'),
        Item('view_file', 'View File...', 'showFileViewer'),
        Item('program', 'Program Loaded File', 'programLoadedFile', accelerator='Ctrl+P'),
        Item('loaded', 'No file loaded', state=DISABLED),     # names the loaded file
        Item('close_file', 'Close File', 'closeLoadedFile'),
    ], postcommand='refreshFileMenu'),
    Submenu('scripts', 'Scripts', [
        Item('run_command', 'Run Command Script...', 'runScript'),
        Item('run_python', 'Run Python Script...', 'runPythonScript'),
        Separator(),
        Item('stop', 'Stop Script  (Esc)', 'stopScript'),
        Separator(),
        # what Run Command Script shows (saved in the settings)
        Check('show_listing', 'Show Script Listing Before Running', 'scriptListingVar', 'setScriptOptions'),
        Check('show_comments', 'Show Script Comments While Running', 'scriptCommentsVar', 'setScriptOptions'),
    ]),
    Separator(),
    Item('save_log', 'Save Terminal Log...', 'saveTerminalLog'),
    Separator(),
    # File > Parameters: save / load / reset the entry-box values of the Erase, Program and
    # Read panels (the only settings that are NOT saved automatically)
    Submenu('parameters', 'Parameters', [
        Item('save', 'Save', 'saveParams'),
        Item('load', 'Load', 'loadParams'),
        Item('defaults', 'Defaults', 'defaultParams'),
    ]),
    Separator(),
    Item('exit', 'Exit', 'onClose'),
]

# View menu: panel visibility, window appearance and Terminal colours.
# (Radio items mark the current choice.)
VIEW = [
    Item('panels', 'Hide Panels (Erase/Program/Read)', 'onPanelToggle'),   # the label follows the state
    Separator(),
    Submenu('appearance', 'Appearance', [
        Radio('light', 'Light', 'light', 'appearanceVar', 'setAppearance'),
        Radio('dark', 'Dark', 'dark', 'appearanceVar', 'setAppearance'),
        Radio('system', 'System (follow Windows)', 'system', 'appearanceVar', 'setAppearance'),
    ]),
    Item('terminal', 'Terminal...', 'showTerminalDialog'),
    Item('hexdump', 'Hex Dump...', 'showHexDialog'),
    Submenu('menu_size', 'Menu text size', [
        Radio('small', 'Small', 'small', 'menuSizeVar', 'setMenuSize'),
        Radio('normal', 'Normal', 'normal', 'menuSizeVar', 'setMenuSize'),
        Radio('large', 'Large', 'large', 'menuSizeVar', 'setMenuSize'),
    ]),
]

HELP = [
    Item('help', 'Help', 'showHelp', accelerator='F1'),
    # Help > Documents: one entry for every file in the docs folder (see dubLibs/documents.py)
    Submenu('documents', 'Documents', postcommand='refreshDocs'),
    Item('datasheet', 'Datasheet', 'openDatasheet'),
    Item('datasheet_source', 'Datasheet Source...', 'editDatasheetUrl'),
    # Help > Assistant: chat window backed by dubLibs/assistant.py. It answers from the help
    # and proposes scripts; nothing runs without the user's OK.
    Item('assistant', 'Assistant...', 'showAssistant'),
    Item('assistant_settings', 'Assistant Settings...', 'showAssistantSettings'),
    Separator(),
    Item('about', 'About', 'showAbout'),
]

# The menus of the menu bar, left to right. Tools: one entry for every script in the tools
# folder that has a "# TOOL: name" header (see dubLibs/tools.py), made when the menu opens.
MENUS = [
    Submenu('file', 'File', FILE),
    Submenu('tools', 'Tools', postcommand='refreshTools'),
    Submenu('view', 'View', VIEW),
    Submenu('help', 'Help', HELP),
]
