"""Help > Assistant: a chat window backed by dubLibs/assistant.py, and the window
that shows a script the assistant proposes. Nothing runs without the user's OK."""
import os
import queue
import re
import threading
from tkinter import END, EW, NSEW
from tkinter.messagebox import showwarning
import customtkinter as ctk
from dubGui.look import newToplevel, showCentered


class ScriptReview:
    """Shows a proposed script; Run saves it and starts it, Save only saves it.
    The outcome is reported back to the assistant (ai.note). win is the window.
    root: the parent window. proposal: dict with title, summary, code and
    destructive. assistantFolder(): the folder scripts are saved in.
    scriptReady(): True if a script may be started now. executePython(path):
    runs a script file. showStatus(text, ms): shows a line in the status bar."""

    def __init__(self, root, proposal, ai, assistantFolder, scriptReady,
                 executePython, showStatus):
        self.proposal = proposal
        self.title = proposal.get('title', 'script')
        self.code = proposal.get('code', '')
        self.ai = ai
        self.assistantFolder = assistantFolder
        self.scriptReady = scriptReady
        self.executePython = executePython
        self.showStatus = showStatus
        self.win = newToplevel(root)
        self.win.title(f'Proposed script: {self.title}')
        self.win.transient(root)
        self.win.geometry('760x560')
        self.win.grid_columnconfigure(0, weight=1)
        self.win.grid_rowconfigure(1, weight=1)
        self.font = ctk.CTkFont(size=14)
        self.buildText()
        self.buildButtons()
        self.win.protocol('WM_DELETE_WINDOW', self.cancel)
        showCentered(self.win, root, size=(760, 560))
        self.win.after(150, self.win.focus_set)

    def buildText(self):
        warn = ('  This changes the board or the flash.'
                if self.proposal.get('destructive') else '')
        ctk.CTkLabel(self.win, text=self.proposal.get('summary', '') + warn,
                     font=self.font, justify='left', anchor='w', wraplength=720,
                     text_color='#c0392b' if warn else None
                     ).grid(row=0, column=0, padx=16, pady=(14, 6), sticky='w')
        box = ctk.CTkTextbox(self.win, font=ctk.CTkFont(family='Consolas', size=13),
                             wrap='none')
        box.grid(row=1, column=0, padx=16, pady=4, sticky=NSEW)
        box.insert('1.0', self.code)
        box.configure(state='disabled')

    def buildButtons(self):
        bar = ctk.CTkFrame(self.win, fg_color='transparent')
        bar.grid(row=2, column=0, padx=16, pady=(6, 14), sticky='e')
        for col, (label, cmd) in enumerate(
                (('Run', self.run), ('Save only', self.keep), ('Reject', self.cancel))):
            ctk.CTkButton(bar, text=label, width=100, font=self.font, command=cmd
                          ).grid(row=0, column=col, padx=(8, 0))

    def save(self):
        name = re.sub(r'[^\w.-]+', '_', self.title).strip('_') or 'script'
        path = os.path.join(self.assistantFolder(), f'{name}.py')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(self.code)
        return path

    def run(self):
        if not self.scriptReady():
            showwarning('Assistant', 'The board is not connected or a '
                        'script is already running.')
            return
        path = self.save()
        self.win.destroy()
        self.ai.note(f'user ran "{self.title}"')
        self.executePython(path)
        self.ai.note(f'"{self.title}" finished; see the Terminal for its output')

    def keep(self):
        path = self.save()
        self.ai.note(f'user saved "{self.title}" without running it')
        self.win.destroy()
        self.showStatus(f'Saved {path}', 6000)

    def cancel(self):
        self.ai.note(f'user rejected "{self.title}"')
        self.win.destroy()


class AssistantWindow:
    """The chat window; win is the window. root: the parent window. ai: the
    assistant (ask, reset, note). review(proposal, ai): shows a proposed script."""

    def __init__(self, root, ai, review):
        self.ai = ai
        self.review = review
        self.inbox = queue.Queue()      # what the worker thread has to show
        self.win = newToplevel(root)
        self.win.title('Dubrovnik Assistant')
        self.win.geometry('640x560')
        self.win.grid_columnconfigure(0, weight=1)
        self.win.grid_rowconfigure(0, weight=1)
        self.font = ctk.CTkFont(size=14)
        self.buildWidgets()
        self.say('Assistant', 'Ask me about the board or the Tiberias commands, or '
                 'describe a test and I will write a script. Nothing runs until '
                 'you approve it.')
        self.poll()
        showCentered(self.win, root, size=(640, 560))
        self.win.after(200, self.entry.focus_set)

    def buildWidgets(self):
        win, font = self.win, self.font
        self.log = ctk.CTkTextbox(win, font=font, wrap='word', state='disabled')
        self.log.grid(row=0, column=0, columnspan=3, padx=10, pady=(10, 4),
                      sticky=NSEW)
        self.entry = ctk.CTkEntry(win, font=font, placeholder_text=
                                  'Ask about the board, or describe a test to script')
        self.entry.grid(row=1, column=0, padx=(10, 4), pady=(4, 10), sticky=EW)
        self.send = ctk.CTkButton(win, text='Send', width=80, font=font,
                                  command=self.sendMessage)
        self.send.grid(row=1, column=1, padx=4, pady=(4, 10))
        ctk.CTkButton(win, text='New chat', width=90, font=font,
                      command=self.newChat).grid(row=1, column=2, padx=(4, 10),
                                                 pady=(4, 10))
        self.entry.bind('<Return>', self.sendMessage)

    def say(self, who, text):
        self.log.configure(state='normal')
        self.log.insert(END, f'{who}: {text}\n\n')
        self.log.configure(state='disabled')
        self.log.see(END)

    def worker(self, text):
        """Runs in a thread: asks the assistant and queues what comes back"""
        try:
            self.ai.ask(text, lambda t: self.inbox.put(('text', t)),
                        lambda p: self.inbox.put(('script', p)))
        except Exception as e:
            self.inbox.put(('error', f'{type(e).__name__}: {e}'))
        self.inbox.put(('done', None))

    def poll(self):
        """Every 100 ms: shows what the worker thread has queued"""
        if not self.win.winfo_exists():
            return
        try:
            while True:
                kind, payload = self.inbox.get_nowait()
                if kind == 'text':
                    self.say('Assistant', payload)
                elif kind == 'script':
                    self.say('Assistant', f'Proposed script "{payload.get("title")}"'
                             ' (review window opened)')
                    self.review(payload, self.ai)
                elif kind == 'error':
                    self.say('Error', payload)
                else:
                    self.send.configure(state='normal')
        except queue.Empty:
            pass
        self.win.after(100, self.poll)

    def sendMessage(self, _event=None):
        text = self.entry.get().strip()
        if not text or self.send.cget('state') == 'disabled':
            return
        self.entry.delete(0, END)
        self.say('You', text)
        self.send.configure(state='disabled')
        threading.Thread(target=self.worker, args=(text,), daemon=True).start()

    def newChat(self):
        self.ai.reset()
        self.log.configure(state='normal')
        self.log.delete('1.0', END)
        self.log.configure(state='disabled')
