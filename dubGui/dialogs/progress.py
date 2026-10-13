"""The progress window of Program: it shows the job running in a thread and
lets the user cancel."""
import time
import customtkinter as ctk


class ProgramCancelled(Exception):
    """Raised by the progress dialog when the user clicks Cancel"""


class ProgressDialog:
    """Modal progress window: show(text, done) is called from a timer while the
    job runs in a thread. cancelled becomes True when Cancel / Esc is used."""

    def __init__(self, root, title, total):
        self.root = root
        self.total, self.cancelled = max(total, 1), False
        self.start = time.time()
        self.win = ctk.CTkToplevel(self.root)
        self.win.title(title)
        self.win.resizable(False, False)
        self.win.transient(self.root)
        font = ctk.CTkFont(size=14)
        self.label = ctk.CTkLabel(self.win, text='Starting...', font=font,
                                  anchor='w', width=420)
        self.label.grid(row=0, column=0, padx=24, pady=(22, 6), sticky='w')
        self.bar = ctk.CTkProgressBar(self.win, width=420)
        self.bar.set(0)
        self.bar.grid(row=1, column=0, padx=24, pady=6)
        self.info = ctk.CTkLabel(self.win, text='', font=font, anchor='w',
                                 width=420)
        self.info.grid(row=2, column=0, padx=24, pady=(0, 6), sticky='w')
        ctk.CTkButton(self.win, text='Cancel', width=100, font=font,
                      command=self.cancel).grid(row=3, column=0, padx=24,
                                                pady=(6, 20), sticky='e')
        self.win.protocol('WM_DELETE_WINDOW', self.cancel)
        self.win.bind('<Escape>', lambda _e: self.cancel())
        self.win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - self.win.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - self.win.winfo_height()) // 2
        self.win.geometry(f'+{max(x, 0)}+{max(y, 0)}')
        self.win.update()
        self.win.grab_set()

    def cancel(self):
        self.cancelled = True
        self.label.configure(text='Cancelling...')

    def show(self, text, done):
        pct = min(done / self.total, 1.0)
        if self.cancelled:
            text = 'Cancelling...'
        self.label.configure(text=text)
        self.bar.set(pct)
        self.info.configure(
            text=f'{pct * 100:.0f} %    {time.time() - self.start:.0f} s elapsed')

    def close(self):
        try:
            self.win.grab_release()
            self.win.destroy()
        except Exception:
            pass
