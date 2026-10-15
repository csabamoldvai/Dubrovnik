"""File > Scripts > Run Command Script: shows the whole script, with line numbers,
before it runs. Run starts it, Cancel (or Esc) does not."""
import customtkinter as ctk
from tkinter import NSEW


def numbered(text):
    """The lines of a script with their line numbers in front, as one text. The
    numbers are as wide as the largest one, so the commands line up."""
    lines = text.splitlines()
    width = len(str(len(lines)))
    return '\n'.join(f'{number:>{width}}  {line}'
                     for number, line in enumerate(lines, 1))


class ScriptPreview:
    """The window is built when the object is created; win is the window.
    root: the parent window. name: the file name. text: the content of the
    script. colours: the Terminal colours (bg, fg). termFont, termFontSize: the
    Terminal font. onRun(): called after the window closed, if Run was chosen."""

    def __init__(self, root, name, text, colours, termFont, termFontSize, onRun):
        self.onRun = onRun
        self.win = ctk.CTkToplevel(root)
        self.win.title(f'Run Command Script: {name}')
        self.win.transient(root)
        self.win.geometry('760x460')
        self.win.grid_columnconfigure(0, weight=1)
        self.win.grid_rowconfigure(0, weight=1)
        self.view = ctk.CTkTextbox(
            self.win, wrap='none', fg_color=colours['bg'], text_color=colours['fg'],
            font=ctk.CTkFont(family=termFont, size=termFontSize))
        self.view.grid(row=0, column=0, padx=10, pady=(10, 4), sticky=NSEW)
        self.view.insert('1.0', numbered(text))
        self.view.configure(state='disabled')       # scrollbars show when the text is long
        self.buildButtons()
        self.win.bind('<Escape>', lambda _e: self.win.destroy())
        self.win.bind('<Return>', lambda _e: self.run())
        self.win.after(150, lambda: (self.win.grab_set(), self.win.focus_set()))

    def buildButtons(self):
        font = ctk.CTkFont(size=14)
        bar = ctk.CTkFrame(self.win, fg_color='transparent')
        bar.grid(row=1, column=0, padx=10, pady=(6, 12), sticky='e')
        ctk.CTkButton(bar, text='Run', width=100, font=font, command=self.run
                      ).grid(row=0, column=0, padx=(8, 0))
        ctk.CTkButton(bar, text='Cancel', width=100, font=font,
                      command=self.win.destroy).grid(row=0, column=1, padx=(8, 0))

    def run(self):
        self.win.destroy()
        self.onRun()
