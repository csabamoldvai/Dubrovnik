"""A small hover message for a widget (used on the entry boxes of the panels)."""
import tkinter as tk
import customtkinter as ctk
from dubGui.look import PAL

DELAY_MS = 500


class Tooltip:
    """Shows text in a small window below widget after the mouse rested on it.
    text is a string or a function returning one (for text that depends on a mode)."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.win = None
        self.timer = None
        widget.bind('<Enter>', self.schedule, add='+')
        widget.bind('<Leave>', self.hide, add='+')
        widget.bind('<ButtonPress>', self.hide, add='+')
        widget.bind('<Destroy>', self.hide, add='+')

    def schedule(self, _event=None):
        self.hide()
        self.timer = self.widget.after(DELAY_MS, self.show)

    def show(self):
        self.timer = None
        text = self.text() if callable(self.text) else self.text
        i = 1 if ctk.get_appearance_mode() == 'Dark' else 0
        win = self.win = tk.Toplevel(self.widget)
        win.wm_overrideredirect(True)
        win.wm_geometry(f'+{self.widget.winfo_rootx()}'
                        f'+{self.widget.winfo_rooty() + self.widget.winfo_height() + 4}')
        tk.Label(win, text=text, justify='left', wraplength=300, padx=6, pady=3,
                 bg=PAL['panel'][i], fg=PAL['text'][i], relief='solid', borderwidth=1
                 ).pack()

    def hide(self, _event=None):
        if self.timer is not None:
            try:
                self.widget.after_cancel(self.timer)
            except tk.TclError:
                pass
            self.timer = None
        if self.win is not None:
            self.win.destroy()
            self.win = None
