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


class TerminalDialog:
    """The window is built when the object is created; win is the window.
    root: the parent window. serCom: holds the Terminal settings (termTheme,
    termBg, termFg, termSelect, termFont, termFontSize) and saves them.
    colors(): the Terminal colours of the chosen theme (bg, fg, select).
    apply(): shows the current settings in the Terminal. installedFonts: the
    fixed-width fonts to offer. defaults: the default settings."""

    def __init__(self, root, serCom, colors, apply, installedFonts, defaults):
        saved = (serCom.termTheme, serCom.termBg, serCom.termFg,
                 serCom.termSelect, serCom.termFont, serCom.termFontSize)
        dlg = ctk.CTkToplevel(root)
        self.win = dlg
        dlg.title('Terminal')
        dlg.resizable(False, False)
        dlg.transient(root)
        font = ctk.CTkFont(size=14)
        themes = (('Auto (follow window)', 'auto'), ('Light', 'light'),
                  ('Dark', 'dark'), ('Custom', 'custom'))
        fonts = list(installedFonts)
        if serCom.termFont not in fonts:
            fonts.insert(0, serCom.termFont)

        def label(row, text):
            ctk.CTkLabel(dlg, text=text, font=font, anchor='w'
                         ).grid(row=row, column=0, padx=(24, 12), pady=6,
                                sticky='w')

        label(0, 'Theme')
        themeMenu = ctk.CTkOptionMenu(
            dlg, values=[t[0] for t in themes], font=font, dropdown_font=font,
            width=240, command=lambda name: pickTheme(name))
        themeMenu.grid(row=0, column=1, columnspan=3, padx=(0, 24), pady=6,
                       sticky='w')

        swatches = {}
        hexEntries = {}
        for row, (key, text, attr) in enumerate((
                ('bg', 'Background', 'termBg'), ('fg', 'Text', 'termFg'),
                ('select', 'Selection', 'termSelect')), start=1):
            label(row, text)
            swatches[key] = ctk.CTkButton(
                dlg, text='', width=60, height=28, border_width=1,
                border_color=PAL['control_border'],
                command=lambda k=key, a=attr: chooseColour(k, a))
            swatches[key].grid(row=row, column=1, padx=(0, 8), pady=6, sticky='w')
            entry = ctk.CTkEntry(dlg, width=100, font=font)
            entry.grid(row=row, column=2, columnspan=2, padx=(0, 24), pady=6,
                       sticky='w')
            entry.bind('<Return>', lambda _e, a=attr, k=key: typedColour(k, a))
            entry.bind('<FocusOut>', lambda _e, a=attr, k=key: typedColour(k, a))
            hexEntries[key] = entry

        label(4, 'Font')
        fontMenu = ctk.CTkOptionMenu(
            dlg, values=fonts, font=font, dropdown_font=font, width=240,
            command=lambda name: pickFont(name))
        fontMenu.grid(row=4, column=1, columnspan=3, padx=(0, 24), pady=6,
                      sticky='w')

        label(5, 'Size')
        ctk.CTkButton(dlg, text='-', width=32, font=font,
                      command=lambda: setSize(serCom.termFontSize - 1)
                      ).grid(row=5, column=1, padx=(0, 4), pady=6, sticky='w')
        sizeEntry = ctk.CTkEntry(dlg, width=56, font=font, justify='center')
        sizeEntry.grid(row=5, column=2, padx=0, pady=6, sticky='w')
        ctk.CTkButton(dlg, text='+', width=32, font=font,
                      command=lambda: setSize(serCom.termFontSize + 1)
                      ).grid(row=5, column=3, padx=(4, 24), pady=6, sticky='w')
        sizeEntry.bind('<Return>', lambda _e: typedSize())
        sizeEntry.bind('<FocusOut>', lambda _e: typedSize())

        preview = ctk.CTkTextbox(dlg, height=110, width=420, wrap='none',
                                 border_width=0)
        preview.grid(row=6, column=0, columnspan=4, padx=24, pady=(10, 4),
                     sticky='ew')
        preview.insert('1.0', '>>> freq 64\nFrequency set to 64 MHz\n'
                       '0000: CA FE 00 00 ')
        preview.insert('end', 'DE AD BE EF', 'picked')
        preview.configure(state='disabled')

        def refresh():
            if not dlg.winfo_exists():
                return
            colours = colors()
            for key, swatch in swatches.items():
                swatch.configure(fg_color=colours[key],
                                 hover_color=colours[key])
                hexEntries[key].delete(0, END)
                hexEntries[key].insert(0, colours[key].upper())
            themeMenu.set(next(n for n, v in themes if v == serCom.termTheme))
            fontMenu.set(serCom.termFont)
            sizeEntry.delete(0, END)
            sizeEntry.insert(0, str(serCom.termFontSize))
            preview.configure(fg_color=colours['bg'], text_color=colours['fg'],
                              font=ctk.CTkFont(family=serCom.termFont,
                                               size=serCom.termFontSize))
            preview._textbox.tag_configure(
                'picked', background=colours['select'], foreground=colours['fg'])
            apply()

        def pickTheme(name):
            serCom.termTheme = dict(themes)[name]
            refresh()

        def setColour(attr, value):
            # editing any colour switches to the Custom theme, starting from
            # the colours that are shown now
            colours = colors()
            serCom.termBg, serCom.termFg = colours['bg'], colours['fg']
            serCom.termSelect = colours['select']
            setattr(serCom, attr, value.lower())
            serCom.termTheme = 'custom'
            refresh()

        def chooseColour(key, attr):
            _rgb, value = askcolor(color=colors()[key], parent=dlg,
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
                    and text.lower() != colors()[key].lower()):
                setColour(attr, text)
            else:
                refresh()      # unchanged or not a colour: show the real value

        def pickFont(name):
            serCom.termFont = name
            refresh()

        def setSize(value):
            serCom.termFontSize = min(max(value, TERM_SIZE_MIN), TERM_SIZE_MAX)
            refresh()

        def typedSize():
            if not dlg.winfo_exists():
                return
            try:
                setSize(int(sizeEntry.get().strip()))
            except ValueError:
                refresh()

        def reset():
            serCom.termTheme = 'dark'
            serCom.termBg = defaults['terminalBg']
            serCom.termFg = defaults['terminalFg']
            serCom.termSelect = defaults['terminalSelect']
            serCom.termFont = defaults['terminalFont']
            serCom.termFontSize = defaults['terminalFontSize']
            refresh()

        def ok():
            serCom.saveConfig()
            dlg.destroy()

        def cancel():
            (serCom.termTheme, serCom.termBg, serCom.termFg, serCom.termSelect,
             serCom.termFont, serCom.termFontSize) = saved
            apply()
            dlg.destroy()

        bar = ctk.CTkFrame(dlg, fg_color='transparent')
        bar.grid(row=7, column=0, columnspan=4, padx=24, pady=(8, 20),
                 sticky='ew')
        bar.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(bar, text='Reset to defaults', width=140, font=font,
                      command=reset).grid(row=0, column=0, sticky='w')
        ctk.CTkButton(bar, text='OK', width=90, font=font, command=ok
                      ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(bar, text='Cancel', width=90, font=font, command=cancel
                      ).grid(row=0, column=2, padx=(8, 0))
        dlg.bind('<Escape>', lambda _e: cancel())
        dlg.protocol('WM_DELETE_WINDOW', cancel)

        refresh()
        dlg.update_idletasks()
        x = root.winfo_x() + (root.winfo_width() - dlg.winfo_width()) // 2
        y = root.winfo_y() + (root.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f'+{max(x, 0)}+{max(y, 0)}')
        dlg.after(150, lambda: (dlg.grab_set(), dlg.focus_set()))
