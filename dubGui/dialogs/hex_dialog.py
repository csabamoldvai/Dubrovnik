"""View > Hex Dump...: the layout of the Hex Dump display mode of the Read panel,
with a sample. Nothing changes until OK."""
from tkinter import END, IntVar, StringVar
import customtkinter as ctk
from dubGui.look import CHECKBOX_STYLE
from dubLibs import hexdump


class HexDialog:
    """The window is built when the object is created; win is the window.
    root: the parent window. settings: holds the settings (hexRow, hexAscii,
    hexUpper, hexGap and the Terminal font) and saves them. colors(): the
    Terminal colours (bg, fg, select). defaults: the default settings."""

    def __init__(self, root, settings, colors, defaults):
        dlg = ctk.CTkToplevel(root)
        self.win = dlg
        dlg.title('Hex Dump')
        dlg.resizable(False, False)
        dlg.transient(root)
        font = ctk.CTkFont(size=14)
        rows = tuple(str(n) for n in hexdump.ROW_SIZES)
        rowVar = StringVar(value=str(settings.hexRow))
        asciiVar = IntVar(value=int(settings.hexAscii))
        upperVar = IntVar(value=int(settings.hexUpper))
        gapVar = IntVar(value=int(settings.hexGap))
        sample = b'Dubrovnik hex dump: \x00\x01\x7f\xff 0123456789'

        ctk.CTkLabel(dlg, text='Bytes per row', font=font, anchor='w'
                     ).grid(row=0, column=0, padx=(24, 12), pady=6, sticky='w')
        ctk.CTkOptionMenu(dlg, values=rows, variable=rowVar, font=font,
                          dropdown_font=font, width=100,
                          command=lambda _v: refresh()
                          ).grid(row=0, column=1, padx=(0, 24), pady=6, sticky='w')
        for row, (text, var) in enumerate((
                ('ASCII column', asciiVar),
                ('Upper case hex digits', upperVar),
                ('Extra space after every 8 bytes', gapVar)), start=1):
            ctk.CTkCheckBox(dlg, **CHECKBOX_STYLE, text=text, variable=var,
                            font=font, command=lambda: refresh()
                            ).grid(row=row, column=0, columnspan=2, padx=24,
                                   pady=6, sticky='w')
        preview = ctk.CTkTextbox(dlg, height=130, width=660, wrap='none',
                                 border_width=0)
        preview.grid(row=4, column=0, columnspan=2, padx=24, pady=(10, 4),
                     sticky='ew')

        def current():
            return dict(per_row=int(rowVar.get()), show_ascii=bool(asciiVar.get()),
                        upper=bool(upperVar.get()), gap=bool(gapVar.get()))

        def refresh():
            colours = colors()
            preview.configure(
                state='normal', fg_color=colours['bg'], text_color=colours['fg'],
                font=ctk.CTkFont(family=settings.termFont, size=settings.termFontSize))
            preview.delete('1.0', END)
            preview.insert('1.0', hexdump.format_hexdump(sample, 0x2005, **current()))
            preview.configure(state='disabled')

        def reset():
            rowVar.set(str(defaults['hexBytesPerRow']))
            asciiVar.set(int(defaults['hexAscii']))
            upperVar.set(int(defaults['hexUpper']))
            gapVar.set(int(defaults['hexGap']))
            refresh()

        def ok():
            values = current()
            settings.hexRow, settings.hexAscii = values['per_row'], values['show_ascii']
            settings.hexUpper, settings.hexGap = values['upper'], values['gap']
            settings.save()
            dlg.destroy()

        bar = ctk.CTkFrame(dlg, fg_color='transparent')
        bar.grid(row=5, column=0, columnspan=2, padx=24, pady=(8, 20), sticky='ew')
        bar.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(bar, text='Reset to defaults', width=140, font=font,
                      command=reset).grid(row=0, column=0, sticky='w')
        ctk.CTkButton(bar, text='OK', width=90, font=font, command=ok
                      ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(bar, text='Cancel', width=90, font=font,
                      command=dlg.destroy).grid(row=0, column=2, padx=(8, 0))
        dlg.bind('<Escape>', lambda _e: dlg.destroy())
        refresh()
        dlg.update_idletasks()
        x = root.winfo_x() + (root.winfo_width() - dlg.winfo_width()) // 2
        y = root.winfo_y() + (root.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f'+{max(x, 0)}+{max(y, 0)}')
        dlg.after(150, lambda: (dlg.grab_set(), dlg.focus_set()))
