"""Help > Assistant: a chat window backed by dubLibs/assistant.py, and the window
that shows a script the assistant proposes. Nothing runs without the user's OK."""
import os
import re
from tkinter import END, EW, NSEW
from tkinter.messagebox import showwarning
import customtkinter as ctk


class ScriptReview:
    """Shows a proposed script; Run saves it and starts it, Save only saves it.
    The outcome is reported back to the assistant (ai.note). win is the window.
    root: the parent window. proposal: dict with title, summary, code and
    destructive. assistantFolder(): the folder scripts are saved in.
    scriptReady(): True if a script may be started now. executePython(path):
    runs a script file. showStatus(text, ms): shows a line in the status bar."""

    def __init__(self, root, proposal, ai, assistantFolder, scriptReady,
                 executePython, showStatus):
        title = proposal.get('title', 'script')
        code = proposal.get('code', '')
        dlg = ctk.CTkToplevel(root)
        self.win = dlg
        dlg.title(f'Proposed script: {title}')
        dlg.transient(root)
        dlg.geometry('760x560')
        dlg.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(1, weight=1)
        font = ctk.CTkFont(size=14)
        warn = ('  This changes the board or the flash.'
                if proposal.get('destructive') else '')
        ctk.CTkLabel(dlg, text=proposal.get('summary', '') + warn, font=font,
                     justify='left', anchor='w', wraplength=720,
                     text_color='#c0392b' if warn else None
                     ).grid(row=0, column=0, padx=16, pady=(14, 6), sticky='w')
        box = ctk.CTkTextbox(dlg, font=ctk.CTkFont(family='Consolas', size=13),
                             wrap='none')
        box.grid(row=1, column=0, padx=16, pady=4, sticky=NSEW)
        box.insert('1.0', code)
        box.configure(state='disabled')

        def save():
            name = re.sub(r'[^\w.-]+', '_', title).strip('_') or 'script'
            path = os.path.join(assistantFolder(), f'{name}.py')
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(code)
            return path

        def run():
            if not scriptReady():
                showwarning('Assistant', 'The board is not connected or a '
                            'script is already running.')
                return
            path = save()
            dlg.destroy()
            ai.note(f'user ran "{title}"')
            executePython(path)
            ai.note(f'"{title}" finished; see the Terminal for its output')

        def keep():
            path = save()
            ai.note(f'user saved "{title}" without running it')
            dlg.destroy()
            showStatus(f'Saved {path}', 6000)

        def cancel():
            ai.note(f'user rejected "{title}"')
            dlg.destroy()

        bar = ctk.CTkFrame(dlg, fg_color='transparent')
        bar.grid(row=2, column=0, padx=16, pady=(6, 14), sticky='e')
        for col, (label, cmd) in enumerate(
                (('Run', run), ('Save only', keep), ('Reject', cancel))):
            ctk.CTkButton(bar, text=label, width=100, font=font, command=cmd
                          ).grid(row=0, column=col, padx=(8, 0))
        dlg.protocol('WM_DELETE_WINDOW', cancel)
        dlg.after(150, dlg.focus_set)


class AssistantWindow:
    """The chat window; win is the window. root: the parent window. ai: the
    assistant (ask, reset, note). review(proposal, ai): shows a proposed script."""

    def __init__(self, root, ai, review):
        import queue
        import threading
        inbox = queue.Queue()
        win = ctk.CTkToplevel(root)
        self.win = win
        win.title('Dubrovnik Assistant')
        win.geometry('640x560')
        win.grid_columnconfigure(0, weight=1)
        win.grid_rowconfigure(0, weight=1)
        font = ctk.CTkFont(size=14)
        log = ctk.CTkTextbox(win, font=font, wrap='word', state='disabled')
        log.grid(row=0, column=0, columnspan=3, padx=10, pady=(10, 4),
                 sticky=NSEW)
        entry = ctk.CTkEntry(win, font=font, placeholder_text=
                             'Ask about the board, or describe a test to script')
        entry.grid(row=1, column=0, padx=(10, 4), pady=(4, 10), sticky=EW)

        def say(who, text):
            log.configure(state='normal')
            log.insert(END, f'{who}: {text}\n\n')
            log.configure(state='disabled')
            log.see(END)

        def worker(text):
            try:
                ai.ask(text, lambda t: inbox.put(('text', t)),
                       lambda p: inbox.put(('script', p)))
            except Exception as e:
                inbox.put(('error', f'{type(e).__name__}: {e}'))
            inbox.put(('done', None))

        def poll():
            if not win.winfo_exists():
                return
            try:
                while True:
                    kind, payload = inbox.get_nowait()
                    if kind == 'text':
                        say('Assistant', payload)
                    elif kind == 'script':
                        say('Assistant', f'Proposed script "{payload.get("title")}"'
                            ' (review window opened)')
                        review(payload, ai)
                    elif kind == 'error':
                        say('Error', payload)
                    else:
                        send.configure(state='normal')
            except queue.Empty:
                pass
            win.after(100, poll)

        def sendMessage(_event=None):
            text = entry.get().strip()
            if not text or send.cget('state') == 'disabled':
                return
            entry.delete(0, END)
            say('You', text)
            send.configure(state='disabled')
            threading.Thread(target=worker, args=(text,), daemon=True).start()

        def newChat():
            ai.reset()
            log.configure(state='normal')
            log.delete('1.0', END)
            log.configure(state='disabled')

        send = ctk.CTkButton(win, text='Send', width=80, font=font,
                             command=sendMessage)
        send.grid(row=1, column=1, padx=4, pady=(4, 10))
        ctk.CTkButton(win, text='New chat', width=90, font=font,
                      command=newChat).grid(row=1, column=2, padx=(4, 10),
                                            pady=(4, 10))
        entry.bind('<Return>', sendMessage)
        say('Assistant', 'Ask me about the board or the Tiberias commands, or '
            'describe a test and I will write a script. Nothing runs until '
            'you approve it.')
        poll()
        win.after(200, entry.focus_set)
