"""The base of the panels: a frame with a title."""
import customtkinter as ctk
from dubGui.look import PANEL_BORDER


class LabeledFrame(ctk.CTkFrame):
    """CTkFrame with a title label at row 0 -- a stand-in for tk.LabelFrame.
    Subclasses should grid their content starting at row=1.
    """

    def __init__(self, master=None, text='', **kwargs):
        kwargs.setdefault('border_width', PANEL_BORDER)
        super().__init__(master, **kwargs)
        self._title = ctk.CTkLabel(
            self, text=text, anchor='w',
            font=ctk.CTkFont(weight='bold'))
        self._title.grid(row=0, column=0, columnspan=99,
                         padx=10, pady=(8, 4), sticky='w')

    def configure_title(self, text):
        self._title.configure(text=text)
