"""View > Terminal...: theme, colours, font and size of the Terminal, with a
preview. Changes show in the Terminal at once; Cancel puts the old look back."""
import re
from tkinter import END
from tkinter.colorchooser import askcolor
import customtkinter as ctk
from dubGui.look import PAL
from dubLibs import termstyle

TERM_SIZE_MIN, TERM_SIZE_MAX = termstyle.SIZE_MIN, termstyle.SIZE_MAX
HEX_COLOR = termstyle.HEX_COLOR

THEMES = (('Auto (follow window)', 'auto'), ('Light', 'light'),
          ('Dark', 'dark'), ('Custom', 'custom'))


class TerminalDialog:
    """The window is built when the object is created; win is the window.
    root: the parent window. settings: holds the Terminal settings (termTheme,
    termBg, termFg, termSelect, termFont, termFontSize) and saves them.
    colors(): the Terminal colours of the chosen theme (bg, fg, select).
    apply(): shows the current settings in the Terminal. installedFonts: the
    fixed-width fonts to offer. defaults: the default settings."""

    def __init__(self, root, settings, colors, apply, installedFonts, defaults):
        self.root = root
        self.settings = settings
        self.colors = colors
        self.apply = apply
        self.defaults = defaults
        self.saved = (settings.termTheme, settings.termBg, settings.termFg,
                      settings.termSelect, settings.termFont, settings.termFontSize)
        self.fonts = list(installedFonts)
        if settings.termFont not in self.fonts:
            self.fonts.insert(0, settings.termFont)
        self.swatches = {}
        self.hexEntries = {}

        self.win = ctk.CTkToplevel(root)
        self.win.title('Terminal')
        self.win.resizable(False, False)
        self.win.transient(root)
        self.font = ctk.CTkFont(size=14)

        self.buildThemeAndColours()
        self.buildFontAndSize()
        self.buildPreview()
        self.buildButtons()
        self.refresh()
        self.centerOnRoot()

    # ---- the widgets

    def label(self, row, text):
        ctk.CTkLabel(self.win, text=text, font=self.font, anchor='w'
                     ).grid(row=row, column=0, padx=(24, 12), pady=6, sticky='w')

    def buildThemeAndColours(self):
        self.label(0, 'Theme')
        self.themeMenu = ctk.CTkOptionMenu(
            self.win, values=[t[0] for t in THEMES], font=self.font,
            dropdown_font=self.font, width=240, command=self.pickTheme)
        self.themeMenu.grid(row=0, column=1, columnspan=3, padx=(0, 24), pady=6,
                            sticky='w')
        for row, (key, text, attr) in enumerate((
                ('bg', 'Background', 'termBg'), ('fg', 'Text', 'termFg'),
                ('select', 'Selection', 'termSelect')), start=1):
            self.label(row, text)
            swatch = ctk.CTkButton(
                self.win, text='', width=60, height=28, border_width=1,
                border_color=PAL['control_border'],
                command=lambda k=key, a=attr: self.chooseColour(k, a))
            swatch.grid(row=row, column=1, padx=(0, 8), pady=6, sticky='w')
            self.swatches[key] = swatch
            entry = ctk.CTkEntry(self.win, width=100, font=self.font)
            entry.grid(row=row, column=2, columnspan=2, padx=(0, 24), pady=6,
                       sticky='w')
            entry.bind('<Return>', lambda _e, a=attr, k=key: self.typedColour(k, a))
            entry.bind('<FocusOut>', lambda _e, a=attr, k=key: self.typedColour(k, a))
            self.hexEntries[key] = entry

    def buildFontAndSize(self):
        win, font, settings = self.win, self.font, self.settings
        self.label(4, 'Font')
        self.fontMenu = ctk.CTkOptionMenu(
            win, values=self.fonts, font=font, dropdown_font=font, width=240,
            command=self.pickFont)
        self.fontMenu.grid(row=4, column=1, columnspan=3, padx=(0, 24), pady=6,
                           sticky='w')

        self.label(5, 'Size')
        ctk.CTkButton(win, text='-', width=32, font=font,
                      command=lambda: self.setSize(settings.termFontSize - 1)
                      ).grid(row=5, column=1, padx=(0, 4), pady=6, sticky='w')
        self.sizeEntry = ctk.CTkEntry(win, width=56, font=font, justify='center')
        self.sizeEntry.grid(row=5, column=2, padx=0, pady=6, sticky='w')
        ctk.CTkButton(win, text='+', width=32, font=font,
                      command=lambda: self.setSize(settings.termFontSize + 1)
                      ).grid(row=5, column=3, padx=(4, 24), pady=6, sticky='w')
        self.sizeEntry.bind('<Return>', lambda _e: self.typedSize())
        self.sizeEntry.bind('<FocusOut>', lambda _e: self.typedSize())

    def buildPreview(self):
        self.preview = ctk.CTkTextbox(self.win, height=110, width=420, wrap='none',
                                      border_width=0)
        self.preview.grid(row=6, column=0, columnspan=4, padx=24, pady=(10, 4),
                          sticky='ew')
        self.preview.insert('1.0', '>>> freq 64\nFrequency set to 64 MHz\n'
                            '0000: CA FE 00 00 ')
        self.preview.insert('end', 'DE AD BE EF', 'picked')
        self.preview.configure(state='disabled')

    def buildButtons(self):
        bar = ctk.CTkFrame(self.win, fg_color='transparent')
        bar.grid(row=7, column=0, columnspan=4, padx=24, pady=(8, 20), sticky='ew')
        bar.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(bar, text='Reset to defaults', width=140, font=self.font,
                      command=self.reset).grid(row=0, column=0, sticky='w')
        ctk.CTkButton(bar, text='OK', width=90, font=self.font, command=self.ok
                      ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(bar, text='Cancel', width=90, font=self.font, command=self.cancel
                      ).grid(row=0, column=2, padx=(8, 0))
        self.win.bind('<Escape>', lambda _e: self.cancel())
        self.win.protocol('WM_DELETE_WINDOW', self.cancel)

    def centerOnRoot(self):
        win, root = self.win, self.root
        win.update_idletasks()
        x = root.winfo_x() + (root.winfo_width() - win.winfo_width()) // 2
        y = root.winfo_y() + (root.winfo_height() - win.winfo_height()) // 2
        win.geometry(f'+{max(x, 0)}+{max(y, 0)}')
        win.after(150, lambda: (win.grab_set(), win.focus_set()))

    # ---- showing the settings

    def refresh(self):
        """Shows the settings in the widgets, the preview and the Terminal"""
        if not self.win.winfo_exists():
            return
        settings = self.settings
        colours = self.colors()
        for key, swatch in self.swatches.items():
            swatch.configure(fg_color=colours[key], hover_color=colours[key])
            self.hexEntries[key].delete(0, END)
            self.hexEntries[key].insert(0, colours[key].upper())
        self.themeMenu.set(next(n for n, v in THEMES if v == settings.termTheme))
        self.fontMenu.set(settings.termFont)
        self.sizeEntry.delete(0, END)
        self.sizeEntry.insert(0, str(settings.termFontSize))
        self.preview.configure(fg_color=colours['bg'], text_color=colours['fg'],
                               font=ctk.CTkFont(family=settings.termFont,
                                                size=settings.termFontSize))
        self.preview._textbox.tag_configure(
            'picked', background=colours['select'], foreground=colours['fg'])
        self.apply()

    # ---- the user's changes

    def pickTheme(self, name):
        self.settings.termTheme = dict(THEMES)[name]
        self.refresh()

    def setColour(self, attr, value):
        # editing any colour switches to the Custom theme, starting from
        # the colours that are shown now
        settings = self.settings
        colours = self.colors()
        settings.termBg, settings.termFg = colours['bg'], colours['fg']
        settings.termSelect = colours['select']
        setattr(settings, attr, value.lower())
        settings.termTheme = 'custom'
        self.refresh()

    def chooseColour(self, key, attr):
        _rgb, value = askcolor(color=self.colors()[key], parent=self.win,
                               title='Terminal colour')
        if value:
            self.setColour(attr, value)

    def typedColour(self, key, attr):
        if not self.win.winfo_exists():
            return
        text = self.hexEntries[key].get().strip()
        if re.fullmatch(r'[0-9a-fA-F]{6}', text):
            text = '#' + text
        if (HEX_COLOR.fullmatch(text)
                and text.lower() != self.colors()[key].lower()):
            self.setColour(attr, text)
        else:
            self.refresh()      # unchanged or not a colour: show the real value

    def pickFont(self, name):
        self.settings.termFont = name
        self.refresh()

    def setSize(self, value):
        self.settings.termFontSize = min(max(value, TERM_SIZE_MIN), TERM_SIZE_MAX)
        self.refresh()

    def typedSize(self):
        if not self.win.winfo_exists():
            return
        try:
            self.setSize(int(self.sizeEntry.get().strip()))
        except ValueError:
            self.refresh()

    def reset(self):
        settings, defaults = self.settings, self.defaults
        settings.termTheme = 'dark'
        settings.termBg = defaults['terminalBg']
        settings.termFg = defaults['terminalFg']
        settings.termSelect = defaults['terminalSelect']
        settings.termFont = defaults['terminalFont']
        settings.termFontSize = defaults['terminalFontSize']
        self.refresh()

    def ok(self):
        self.settings.save()
        self.win.destroy()

    def cancel(self):
        settings = self.settings
        (settings.termTheme, settings.termBg, settings.termFg, settings.termSelect,
         settings.termFont, settings.termFontSize) = self.saved
        self.apply()
        self.win.destroy()
