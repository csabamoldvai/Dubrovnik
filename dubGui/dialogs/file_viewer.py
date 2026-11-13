"""File > Image Files > View File: the whole loaded file as a hex dump, at the
addresses it will be written to, with a "Go to address" box."""
import customtkinter as ctk
from dubGui.look import newToplevel, showCentered
from tkinter import NSEW
from tkinter.messagebox import showerror
from dubLibs import hexdump
from dubLibs.fields import parseField


class FileViewer:
    """The window is built when the object is created; win is the window.
    root: the parent window. image: the loaded firmware image (its describe()
    and segments). imageName: the file name. offset: added to every address.
    colours: the Terminal colours (bg, fg, select). termFont, termFontSize: the
    Terminal font. hexOptions: the hex dump layout (keywords of hexdump)."""

    def __init__(self, root, image, imageName, offset, colours,
                 termFont, termFontSize, hexOptions):
        win = newToplevel(root)
        self.win = win
        win.title(f'{imageName}   {image.describe()}   '
                  f'Offset 0x{offset:X}')
        win.geometry('900x600')
        win.grid_columnconfigure(0, weight=1)
        win.grid_rowconfigure(0, weight=1)
        view = ctk.CTkTextbox(
            win, wrap='none', fg_color=colours['bg'], text_color=colours['fg'],
            font=ctk.CTkFont(family=termFont, size=termFontSize))
        view.grid(row=0, column=0, columnspan=4, padx=10, pady=(10, 4),
                  sticky=NSEW)
        text, rows = hexdump.format_segments(image.segments, offset,
                                             **hexOptions)
        view.insert('1.0', text)
        view.configure(state='disabled')
        view._textbox.tag_configure('hit', background=colours['select'])
        font = ctk.CTkFont(size=14)
        ctk.CTkLabel(win, text='Go to address: 0x', font=font
                     ).grid(row=1, column=0, padx=(12, 0), pady=(4, 10), sticky='e')
        entry = ctk.CTkEntry(win, width=120, font=font)
        entry.grid(row=1, column=1, padx=4, pady=(4, 10), sticky='w')

        def go(_event=None):
            try:
                address = parseField('Address', entry.get())
            except ValueError as e:
                showerror('View File', str(e))
                return
            line = hexdump.line_for_address(rows, address)
            if line is None:
                return
            view._textbox.tag_remove('hit', '1.0', 'end')
            view._textbox.tag_add('hit', f'{line}.0', f'{line}.end')
            view._textbox.see(f'{line}.0')
        entry.bind('<Return>', go)
        ctk.CTkButton(win, text='Go', width=70, font=font, command=go
                      ).grid(row=1, column=2, padx=4, pady=(4, 10), sticky='w')
        ctk.CTkButton(win, text='Close', width=90, font=font, command=win.destroy
                      ).grid(row=1, column=3, padx=12, pady=(4, 10), sticky='e')
        win.bind('<Escape>', lambda _e: win.destroy())
        showCentered(win, root, size=(900, 600))
        win.after(150, lambda: (win.lift(), entry.focus_set()))
