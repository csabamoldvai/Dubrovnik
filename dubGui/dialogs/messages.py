"""Small windows in the Workbench look: the About window and a message box with
your own buttons (the standard Windows and Tk dialogs use a small fixed font)."""
from tkinter import END
import customtkinter as ctk
from dubGui.look import PAL, newToplevel, showCentered
from dubLibs.version import VERSION as APP_VERSION


def showAbout(root):
    dlg = newToplevel(root)
    dlg.title('About')
    dlg.resizable(False, False)
    dlg.transient(root)

    ctk.CTkLabel(dlg, text='Dubrovnik Workbench',
                 font=ctk.CTkFont(size=22, weight='bold')
                 ).grid(row=0, column=0, padx=40, pady=(24, 2))
    ctk.CTkLabel(dlg, text=f'Version {APP_VERSION}', text_color=PAL['text_muted']
                 ).grid(row=1, column=0, padx=40, pady=(0, 16))
    ctk.CTkLabel(dlg, text='Authors', font=ctk.CTkFont(weight='bold')
                 ).grid(row=2, column=0, padx=40)
    ctk.CTkLabel(dlg, text=('Csaba Moldvai (System/Board design, GUI)\n'
                            'Eyal Barzilay (Tiberias flash support software)')
                 ).grid(row=3, column=0, padx=40, pady=(2, 16))
    ctk.CTkButton(dlg, text='OK', width=90, command=dlg.destroy
                  ).grid(row=4, column=0, pady=(0, 20))

    # centre over the main window, then make it modal
    showCentered(dlg, root)
    dlg.bind('<Escape>', lambda _e: dlg.destroy())
    dlg.after(100, lambda: (dlg.grab_set(), dlg.focus_set()))


def dialogBox(root, title, text, buttons, entryDefault=None):
    """Modal dialog in the Workbench look and size (the standard Windows and
    Tk dialogs use a small fixed font). buttons: [(label, value), ...], the
    first one is the default (Enter), the last one is what Esc and closing
    the window return. With entryDefault the dialog has a text box and the
    first button returns its text."""
    dlg = newToplevel(root)
    dlg.title(title)
    dlg.resizable(False, False)
    dlg.transient(root)
    result = [buttons[-1][1]]
    font = ctk.CTkFont(size=14)

    ctk.CTkLabel(dlg, text=text, font=font, justify='left', anchor='w',
                 wraplength=520).grid(row=0, column=0, padx=28, pady=(24, 12),
                                      sticky='w')
    entry = None
    row = 1
    if entryDefault is not None:
        entry = ctk.CTkEntry(dlg, width=360, font=font)
        entry.insert(0, entryDefault)
        entry.grid(row=row, column=0, padx=28, pady=(0, 12), sticky='w')
        row += 1

    def finish(value, index):
        if entry is not None and index == 0:
            value = entry.get()
        result[0] = value
        dlg.destroy()

    bar = ctk.CTkFrame(dlg, fg_color='transparent')
    bar.grid(row=row, column=0, padx=28, pady=(4, 22), sticky='e')
    for i, (label, value) in enumerate(buttons):
        ctk.CTkButton(bar, text=label, width=100, font=font,
                      command=lambda v=value, n=i: finish(v, n)
                      ).grid(row=0, column=i, padx=(8, 0))
    dlg.bind('<Return>', lambda _e: finish(buttons[0][1], 0))
    dlg.bind('<Escape>', lambda _e: finish(buttons[-1][1], len(buttons) - 1))
    dlg.protocol('WM_DELETE_WINDOW',
                 lambda: finish(buttons[-1][1], len(buttons) - 1))

    showCentered(dlg, root)

    def focus():
        dlg.grab_set()
        (entry or dlg).focus_set()
        if entry is not None:
            entry.select_range(0, END)
    dlg.after(150, focus)
    root.wait_window(dlg)
    return result[0]
