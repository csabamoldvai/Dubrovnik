"""Preferences > Hex View...: the layout of the Hex View display mode of the Read panel,
with a sample. Nothing changes until OK."""
from tkinter import END, IntVar, StringVar
import customtkinter as ctk
from dubGui.look import CHECKBOX_STYLE, newToplevel, showCentered
from dubLibs import hexdump

SAMPLE = b'Dubrovnik hex dump: \x00\x01\x7f\xff 0123456789'


class HexDialog:
    """The window is built when the object is created; win is the window.
    root: the parent window. settings: holds the settings (hexRow, hexAscii,
    hexUpper, hexGap and the Terminal font) and saves them. colors(): the
    Terminal colours (bg, fg, select). defaults: the default settings."""

    def __init__(self, root, settings, colors, defaults):
        self.root = root
        self.settings = settings
        self.colors = colors
        self.defaults = defaults
        self.win = newToplevel(root)
        self.win.title('Hex View')
        self.win.resizable(False, False)
        self.win.transient(root)
        self.font = ctk.CTkFont(size=14)
        self.rowVar = StringVar(value=str(settings.hexRow))
        self.asciiVar = IntVar(value=int(settings.hexAscii))
        self.upperVar = IntVar(value=int(settings.hexUpper))
        self.gapVar = IntVar(value=int(settings.hexGap))

        self.buildOptions()
        self.buildPreview()
        self.buildButtons()
        self.refresh()
        self.centerOnRoot()

    def buildOptions(self):
        win, font = self.win, self.font
        ctk.CTkLabel(win, text='Bytes per row', font=font, anchor='w'
                     ).grid(row=0, column=0, padx=(24, 12), pady=6, sticky='w')
        ctk.CTkOptionMenu(win, values=[str(n) for n in hexdump.ROW_SIZES],
                          variable=self.rowVar, font=font, dropdown_font=font,
                          width=100, command=lambda _v: self.refresh()
                          ).grid(row=0, column=1, padx=(0, 24), pady=6, sticky='w')
        for row, (text, var) in enumerate((
                ('ASCII column', self.asciiVar),
                ('Upper case hex digits', self.upperVar),
                ('Extra space after every 8 bytes', self.gapVar)), start=1):
            ctk.CTkCheckBox(win, **CHECKBOX_STYLE, text=text, variable=var,
                            font=font, command=self.refresh
                            ).grid(row=row, column=0, columnspan=2, padx=24,
                                   pady=6, sticky='w')

    def buildPreview(self):
        self.preview = ctk.CTkTextbox(self.win, height=130, width=660, wrap='none',
                                      border_width=0)
        self.preview.grid(row=4, column=0, columnspan=2, padx=24, pady=(10, 4),
                          sticky='ew')

    def buildButtons(self):
        bar = ctk.CTkFrame(self.win, fg_color='transparent')
        bar.grid(row=5, column=0, columnspan=2, padx=24, pady=(8, 20), sticky='ew')
        bar.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(bar, text='Reset to defaults', width=140, font=self.font,
                      command=self.reset).grid(row=0, column=0, sticky='w')
        ctk.CTkButton(bar, text='OK', width=90, font=self.font, command=self.ok
                      ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(bar, text='Cancel', width=90, font=self.font,
                      command=self.win.destroy).grid(row=0, column=2, padx=(8, 0))
        self.win.bind('<Escape>', lambda _e: self.win.destroy())

    def centerOnRoot(self):
        win, root = self.win, self.root
        showCentered(win, root)
        win.after(150, lambda: (win.grab_set(), win.focus_set()))

    def current(self):
        """The layout chosen in the window, as the arguments of hexdump.format_hexdump"""
        return dict(per_row=int(self.rowVar.get()), show_ascii=bool(self.asciiVar.get()),
                    upper=bool(self.upperVar.get()), gap=bool(self.gapVar.get()))

    def refresh(self):
        colours = self.colors()
        self.preview.configure(
            state='normal', fg_color=colours['bg'], text_color=colours['fg'],
            font=ctk.CTkFont(family=self.settings.termFont,
                             size=self.settings.termFontSize))
        self.preview.delete('1.0', END)
        self.preview.insert('1.0', hexdump.format_hexdump(SAMPLE, 0x2005, **self.current()))
        self.preview.configure(state='disabled')

    def reset(self):
        defaults = self.defaults
        self.rowVar.set(str(defaults['hexBytesPerRow']))
        self.asciiVar.set(int(defaults['hexAscii']))
        self.upperVar.set(int(defaults['hexUpper']))
        self.gapVar.set(int(defaults['hexGap']))
        self.refresh()

    def ok(self):
        values, settings = self.current(), self.settings
        settings.hexRow, settings.hexAscii = values['per_row'], values['show_ascii']
        settings.hexUpper, settings.hexGap = values['upper'], values['gap']
        settings.save()
        self.win.destroy()
