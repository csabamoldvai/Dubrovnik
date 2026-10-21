"""Preferences > Configure Paths...: the folders the program uses. The editable ones can be
changed (Browse, or type); every folder can be opened in Explorer. Nothing changes until OK."""
import os
from tkinter import StringVar
from tkinter.filedialog import askdirectory
from tkinter.messagebox import showerror
import customtkinter as ctk


class PathRow:
    """One line of the window. key: name used in the result. value: the folder now set
    ('' = the default). default: what '' stands for (shown; may be ''). editable: False for
    folders of the program that only get an Open button. hint: one line of help."""

    def __init__(self, key, label, value, default, editable=True, hint=''):
        self.key, self.label, self.value = key, label, value
        self.default, self.editable, self.hint = default, editable, hint


class PathsDialog:
    """The window is built when the object is created; win is the window.
    root: the parent window. rows: list of PathRow. onOk(values): called with
    {key: folder or ''} for the editable rows when all of them are valid; '' means the
    default."""

    def __init__(self, root, rows, onOk):
        self.root, self.rows, self.onOk = root, rows, onOk
        self.win = ctk.CTkToplevel(root)
        self.win.title('Configure Paths')
        self.win.resizable(False, False)
        self.win.transient(root)
        self.font = ctk.CTkFont(size=14)
        self.small = ctk.CTkFont(size=12)
        self.vars = {}
        for number, row in enumerate(rows):
            self.buildRow(number * 2, row)
        self.buildButtons(len(rows) * 2)
        self.centerOnRoot()

    def buildRow(self, line, row):
        win, font = self.win, self.font
        ctk.CTkLabel(win, text=row.label, font=font, anchor='w').grid(
            row=line, column=0, padx=(24, 12), pady=(10, 0), sticky='w')
        var = StringVar(value=row.value or row.default)
        entry = ctk.CTkEntry(win, textvariable=var, width=470, font=font,
                             state='normal' if row.editable else 'disabled')
        entry.grid(row=line, column=1, padx=(0, 8), pady=(10, 0), sticky='w')
        ctk.CTkButton(win, text='Open', width=70, font=font,
                      command=lambda v=var: self.openFolder(v.get())
                      ).grid(row=line, column=2, padx=(0, 6), pady=(10, 0))
        if row.editable:
            self.vars[row.key] = var
            ctk.CTkButton(win, text='Browse...', width=90, font=font,
                          command=lambda v=var: self.browse(v)
                          ).grid(row=line, column=3, padx=(0, 6), pady=(10, 0))
            ctk.CTkButton(win, text='Default', width=80, font=font,
                          command=lambda v=var, r=row: v.set(r.default)
                          ).grid(row=line, column=4, padx=(0, 24), pady=(10, 0))
        if row.hint:
            ctk.CTkLabel(win, text=row.hint, font=self.small, anchor='w',
                         text_color=('gray35', 'gray65')).grid(
                row=line + 1, column=1, columnspan=4, padx=(0, 24), sticky='w')

    def buildButtons(self, line):
        bar = ctk.CTkFrame(self.win, fg_color='transparent')
        bar.grid(row=line, column=0, columnspan=5, padx=24, pady=(14, 20), sticky='e')
        ctk.CTkButton(bar, text='OK', width=90, font=self.font, command=self.ok
                      ).grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(bar, text='Cancel', width=90, font=self.font,
                      command=self.win.destroy).grid(row=0, column=1)
        self.win.bind('<Escape>', lambda _e: self.win.destroy())

    def centerOnRoot(self):
        win, root = self.win, self.root
        win.update_idletasks()
        x = root.winfo_x() + (root.winfo_width() - win.winfo_width()) // 2
        y = root.winfo_y() + (root.winfo_height() - win.winfo_height()) // 2
        win.geometry(f'+{max(x, 0)}+{max(y, 0)}')
        win.after(150, lambda: (win.grab_set(), win.focus_set()))

    def browse(self, var):
        start = var.get() if os.path.isdir(var.get()) else None
        folder = askdirectory(parent=self.win, initialdir=start, mustexist=True)
        if folder:
            var.set(os.path.normpath(folder))

    def openFolder(self, folder):
        if os.path.isdir(folder):
            os.startfile(folder)
        else:
            showerror('Configure Paths', f'This folder was not found:\n{folder}', parent=self.win)

    def values(self):
        """{key: folder or ''}: the default (or an empty box) is stored as ''"""
        result = {}
        for row in self.rows:
            if row.editable:
                text = self.vars[row.key].get().strip()
                result[row.key] = '' if text == row.default else text
        return result

    def ok(self):
        values = self.values()
        for row in self.rows:
            folder = values.get(row.key)
            if folder and not os.path.isdir(folder):
                showerror('Configure Paths', f'{row.label}\nThis folder was not found:\n{folder}',
                          parent=self.win)
                return
        self.onOk(values)
        self.win.destroy()
