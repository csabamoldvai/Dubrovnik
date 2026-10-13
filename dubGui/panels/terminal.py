"""The Terminal: the command line and the board output at the bottom of the main window."""
import re
from tkinter import END, INSERT, Menu
import customtkinter as ctk
from dubGui.look import TERM_THEMES
from dubGui.panels.base import LabeledFrame
from dubLibs import run_cmd_script

PROMPT = '>>> '
CLEAR_CMD = 'clear'


class Terminal(LabeledFrame):
    def __init__(self, parent, app):
        LabeledFrame.__init__(self, parent, text='Terminal')
        self.app = app
        self.comm = None
        self.history = []
        self.historyIndex = 0
        # CM TODO: check if needed. displayText implemented differently
        self.textToDisplay = None
        # Async serial polling: set True while onReturnKey owns the serial port
        # so the poller doesn't race with comm.send()/response().
        self.cmdInProgress = False
        self.pollIntervalMs = 100

        self.txt = ctk.CTkTextbox(
            self, wrap='char', width=400, height=300,
            font=ctk.CTkFont(family='Consolas', size=15),
            border_width=0)
        self.onZoom = None       # set by the app: onZoom(+1 or -1), Ctrl + wheel
        self.applyColors(TERM_THEMES['dark'])
        self.txt.grid(row=1, column=0, columnspan=99,
                      pady=10, padx=10, sticky="NSEW")

        self.clear()
        self.txt.focus()      # placing cursor in text area

        # Key bindings
        self.txt.bind('<Return>', self.onReturnKey)
        self.txt.bind('<BackSpace>', self.onBackSpace)
        self.txt.bind('<Delete>', self.onDelete)
        self.txt.bind('<Up>', self.onUpArrowKey)
        self.txt.bind('<Down>', self.onDownArrowKey)
        self.txt.bind('<Left>', self.onLeftArrowKey)
        # Typing/pasting is only allowed on the active prompt line
        self.txt.bind('<Key>', self.onKeyPress)
        self.txt.bind('<<Paste>>', self.onPaste)
        self.txt.bind('<<Cut>>', lambda _e: 'break')
        # Ctrl + mouse wheel changes the text size instead of scrolling
        self.txt.bind('<Control-MouseWheel>', self.onCtrlWheel)

        # Right-click context menu
        self.ctxMenu = Menu(self.txt, tearoff=False)
        self.ctxMenu.add_command(label='Clear', command=self.clear)
        self.txt.bind('<Button-3>', self.showContextMenu)

        # Start the async serial poller. It runs forever and no-ops when the
        # port isn't open or a synchronous command is in progress.
        self.after(self.pollIntervalMs, self.pollSerial)

    def onCtrlWheel(self, event):
        if self.onZoom and event.delta:
            self.onZoom(1 if event.delta > 0 else -1)
        return 'break'          # no scrolling

    def setFont(self, family, size):
        self.txt.configure(font=ctk.CTkFont(family=family, size=size))

    def applyColors(self, t):
        """Sets the Terminal colours; t has the keys bg, fg and select"""
        self.txt.configure(fg_color=t['bg'], text_color=t['fg'])
        # tk.Text options CTkTextbox doesn't expose: cursor and selection
        self.txt._textbox.configure(
            insertbackground=t['fg'], selectbackground=t['select'],
            selectforeground=t['fg'])

    def showContextMenu(self, event):
        try:
            # same font as the menu bar (the default Tk menu font is tiny);
            # menuFont is set once the window is built. Multiply the size
            # here to make this menu larger.
            self.ctxMenu.configure(font=(self.app.menuFont[0], int(self.app.menuFont[1] * 1.0)))
            self.ctxMenu.tk_popup(event.x_root, event.y_root)
        finally:
            self.ctxMenu.grab_release()

    def pollSerial(self):
        """Drain bytes that arrived on the serial port asynchronously
        (e.g. boot/reset messages) and print them in the terminal."""
        try:
            handle = getattr(self.comm, 'handle', None)
            if (handle is not None and handle.is_open
                    and not self.cmdInProgress):
                try:
                    n = handle.in_waiting
                except Exception:      # the port vanished: board off or unplugged
                    n = 0
                    self.app.serCom.connectionLost()
                if n > 0:
                    data = handle.read(n).decode('utf-8', errors='replace')
                    data = data.replace('\r', '')
                    if data:
                        self.txt.insert(END, data)
                        self.txt.mark_set(INSERT, END)
                        self.txt.see(INSERT)
                        self.watchBootMessage(data)
        except Exception as e:
            print(f'pollSerial error: {e}')
        finally:
            self.after(self.pollIntervalMs, self.pollSerial)

    def watchBootMessage(self, data):
        """The board detects its device after power-up or RESET and prints a
        banner. Keep the status bar in step with it: 'Detecting flash part'
        clears the device, 'Part info: <part> ...' sets it."""
        self.bootBuf = (getattr(self, 'bootBuf', '') + data)[-2000:]
        if 'Detecting flash part' in self.bootBuf:
            self.app.serCom.deviceDetected('')
            self.bootBuf = self.bootBuf.split('Detecting flash part')[-1]
        m = re.search(r'Part info:\s*(\S+)\s', self.bootBuf)  # whole word received
        if m:
            self.app.serCom.deviceDetected(m.group(1))
            self.bootBuf = ''

    def displayText(self, text):
        self.txt.insert(END, '\n' + text)
        self.txt.insert(END, '\n' + PROMPT)
        self.txt.mark_set(INSERT, END)
        self.txt.see(INSERT)

    def onReturnKey(self, _event):
        if self.app.serCom.scriptRunning:
            return 'break'          # the script owns the board
        cmdstr = self.txt.get("end-1l linestart", "end-1l lineend")[
            len(PROMPT):].strip()
        if len(cmdstr) > 0:
            self.history.append(cmdstr)

        if cmdstr == CLEAR_CMD:
            self.clear()
            return 'break'
        elif len(cmdstr) > 0:
            resp = self.execute(cmdstr)
            if resp != '':
                self.txt.insert(END, '\n' + resp)

        self.txt.insert(END, '\n' + PROMPT)
        self.txt.mark_set(INSERT, END)
        self.txt.see(INSERT)
        self.historyIndex = len(self.history)
        # Returning 'break' prevents the native behavior, i.e. line break.
        return 'break'

    def execute(self, cmdstr):
        """Sends one command to the board and returns the reply text"""
        self.cmdInProgress = True
        try:
            self.comm.send(cmdstr)
            resp = self.comm.response(removeCmd=True, removePrompt=True).strip()
        except Exception as e:
            resp = f'error from boardcom: {e}'
        finally:
            self.cmdInProgress = False
        return resp

    def runScriptCommand(self, cmdstr):
        """Runs cmdstr as if it had been typed (the command and its reply are
        shown in the Terminal) and returns the reply"""
        self.ensureActiveLine()
        self.txt.delete('end-1l linestart+%dc' % len(PROMPT), 'end-1c')
        self.txt.insert(END, cmdstr)
        if cmdstr == CLEAR_CMD:
            self.clear()
            return ''
        resp = self.execute(cmdstr)
        if resp != '':
            self.txt.insert(END, '\n' + resp)
        self.txt.insert(END, '\n' + PROMPT)
        self.txt.mark_set(INSERT, END)
        self.txt.see(INSERT)
        return resp

    def scriptPrint(self, text):
        """Shows a line printed by a script, above the prompt line"""
        self.ensureActiveLine()
        self.txt.delete('end-1l linestart', 'end-1c')     # drop the empty prompt
        self.txt.insert(END, text + '\n' + PROMPT)
        self.txt.mark_set(INSERT, END)
        self.txt.see(INSERT)

    def ensureActiveLine(self):
        """Moves the cursor to the end of the active prompt line unless it is
        already on that line (after the prompt). Returns True if it moved."""
        line, col = map(int, self.txt.index(INSERT).split('.'))
        lastLine = int(self.txt.index('end-1c').split('.')[0])
        if line == lastLine and col >= len(PROMPT):
            return False
        self.txt.tag_remove('sel', '1.0', END)
        self.txt.mark_set(INSERT, 'end-1c')
        self.txt.see(INSERT)
        return True

    def onKeyPress(self, event):
        """Earlier output is read-only (select/copy only): typing a character
        jumps the cursor to the prompt line first; other edits are blocked."""
        ch = event.char
        if ch and ch.isprintable():
            self.ensureActiveLine()      # then the character is inserted there
            return None
        if ch:                           # a control character
            key = event.keysym.lower()
            if key in ('c', 'a'):        # copy / select all
                return None
            if key == 'v':               # paste goes to the prompt line
                self.ensureActiveLine()
                return None
            return 'break'               # Tab, Ctrl+X/Z/Y, ...
        return None                      # navigation and modifier keys

    def onPaste(self, _event):
        """Pastes onto the prompt line as ONE clean command line: no '>>>', no
        line breaks, no invisible characters (see run_cmd_script.clean_pasted)"""
        try:
            text = self.txt.clipboard_get()
        except Exception:               # empty clipboard or not text
            return 'break'
        self.ensureActiveLine()
        self.txt.insert(INSERT, run_cmd_script.clean_pasted(text))
        self.txt.see(INSERT)
        return 'break'

    def onBackSpace(self, _event):
        if self.ensureActiveLine():
            return 'break'               # just jump to the prompt line
        return self.allowDelete(5)

    def onDelete(self, _event):
        if self.ensureActiveLine():
            return 'break'
        return self.allowDelete(4)

    def allowDelete(self, charIndex):
        cur = self.txt.index(INSERT)
        charPos = int(cur.split('.')[1])
        if charPos < charIndex:
            return 'break'  # Returning 'break' prevents the native behavior, e.g. Del

    def onUpArrowKey(self, _event):
        if self.historyIndex > 0:
            self.historyIndex -= 1
        return self.replaceLineWithHistory()

    def onDownArrowKey(self, _event):
        if self.historyIndex < len(self.history):
            self.historyIndex += 1
        return self.replaceLineWithHistory()

    def onLeftArrowKey(self, _event):
        return self.allowDelete(5)

    def replaceLineWithHistory(self):
        self.txt.delete('end-1l linestart+' +
                        str(len(PROMPT)) + 'c', 'end-1l lineend')

        newLine = ''
        if self.historyIndex < len(self.history):
            newLine = self.history[self.historyIndex]
        self.txt.insert(END, newLine)
        return 'break'  # Returning 'break' prevents the native behavior, e.g. Up/Down/Return

    def clear(self):
        self.txt.delete(1.0, END)
        self.txt.insert(1.0, PROMPT)
        self.txt.mark_set(INSERT, END)

    def tprint(self, text, printOn='guiConsole'):
        """Targeted Print\n
        Prints on the targeted console\n
        Input parameters:\n
        text: the text to be printed
        printOn: the target where to print the messages:
            'sysConsole' prints on system console
            'guiConsole' prints in the GUI text window
            'both' prints in both places (it slows down the system)
        """
        if printOn == 'sysConsole':
            print(text)
        elif printOn == 'guiConsole':
            self.displayText(text)
            self.app.du.textToDisplay = ""
        else:
            print(text)
            self.displayText(text)
            self.app.du.textToDisplay = ""

    def callCommand(self):
        pass
