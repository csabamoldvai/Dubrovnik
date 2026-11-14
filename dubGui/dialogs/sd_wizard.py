"""Tools > Program SD Card...: a guide through programming the board's SD card with MfgTool2.

The programming itself is done by NXP's MfgTool2.exe (it has no command line and its result
cannot be read), so this window walks the user through the steps, one page at a time, and does
what can be done safely: copies the chosen boot_image.sb into the tool's profile (the tool looks
for exactly that name), starts the tool, asks how it ended and, after the restart, compares the
build date the board prints at start-up with the release's date (the name of its folder).

Pages: 1 choose the software, 2 prepare the board, 3 start the tool, 4 program, 5 restart,
6 check the version. A page's Next button waits until all its steps are ticked. The helpers of
dubLibs/sd_card.py do the work that needs no window.
"""
import os
import subprocess
from tkinter.filedialog import askopenfilename
from tkinter.messagebox import showerror, showwarning

import customtkinter as ctk

from dubGui.look import newToplevel, showCentered
from dubLibs import sd_card
from dubLibs.settings import default_folder

GREEN, RED, AMBER, GREY = '#2E7D32', '#C62828', '#B26A00', ('gray35', 'gray65')
WRAP = 640
POLL_MS = 500


def launch(exe, folder):
    """Starts the tool (it keeps running on its own). A function of its own so that a check can
    replace it."""
    subprocess.Popen([exe], cwd=folder)


class SdWizard:
    """The window is built when the object is created; win is the window.
    root: the parent window. settings: the Settings object (mfgToolDir, sdImageDir).
    onPaths(): opens Preferences > Configure Paths. log(text): writes a line to the Terminal.
    mark(), textSince(mark): a position in the Terminal text and the text added after it."""

    def __init__(self, root, settings, onPaths, log, mark, textSince):
        self.root, self.settings = root, settings
        self.onPaths, self.log, self.mark, self.textSince = onPaths, log, mark, textSince
        self.chosen = None              # the sd_card.Release that was chosen
        self.release = None             # its date (datetime.date) or None
        self.listed = []                # the releases found in the folder
        self.since = None               # Terminal position when the restart page was shown
        self.verdict = 'unknown'
        self.built = None
        self.index = 0
        self.textColor = ctk.ThemeManager.theme['CTkLabel']['text_color']   # the normal colour
        self.font = ctk.CTkFont(size=14)
        self.bold = ctk.CTkFont(size=18, weight='bold')
        self.win = newToplevel(root)
        self.win.title('Program SD Card')
        self.win.resizable(False, False)
        self.win.transient(root)
        self.body = ctk.CTkFrame(self.win, fg_color='transparent')
        self.body.grid(row=0, column=0, padx=24, pady=(18, 4), sticky='nsew')
        self.pages, self.checks, self.optional = [], [], []     # per page: required / optional ticks
        for number, build in enumerate((self.pageChoose, self.pageBoard, self.pageTool,
                                        self.pageProgram, self.pageRestart, self.pageCheck)):
            frame = ctk.CTkFrame(self.body, fg_color='transparent')
            frame.grid(row=0, column=0, sticky='nsew')      # all pages in one cell: the window
            self.pages.append(frame)                        # is as big as the biggest page
            self.checks.append([])
            self.optional.append([])
            build(frame, number)
        self.buildButtons()
        self.win.protocol('WM_DELETE_WINDOW', self.close)
        self.win.bind('<Escape>', lambda _e: self.close())
        self.fillReleases()
        self.show(0)
        showCentered(self.win, root)
        self.win.after(150, self.win.focus_set)
        self.win.after(POLL_MS, self.poll)

    # ---- building blocks -----------------------------------------------------------------

    def heading(self, frame, number, text):
        ctk.CTkLabel(frame, text=f'Step {number + 1} of 6:  {text}', font=self.bold, anchor='w'
                     ).grid(row=0, column=0, sticky='w', pady=(0, 8))

    def note(self, frame, row, text='', color=None):
        label = ctk.CTkLabel(frame, text=text, font=self.font, anchor='w', justify='left',
                             wraplength=WRAP, text_color=color)
        label.grid(row=row, column=0, sticky='w', pady=(0, 6))
        return label

    def steps(self, frame, number, first_row, texts):
        """A tick box for each step; Next waits until they are all ticked, except the steps that
        start with "[Optional]" (those can be left unticked)"""
        for offset, text in enumerate(texts):
            var = ctk.BooleanVar(value=False)
            box = ctk.CTkCheckBox(frame, text=text, variable=var, font=self.font,
                                  command=self.update)
            box.grid(row=first_row + offset, column=0, sticky='w', pady=3)
            (self.optional if text.startswith('[Optional]') else self.checks)[number].append(var)
        return first_row + len(texts)

    def buttonRow(self, frame, row, buttons):
        bar = ctk.CTkFrame(frame, fg_color='transparent')
        bar.grid(row=row, column=0, sticky='w', pady=(4, 6))
        made = []
        for column, (text, command) in enumerate(buttons):
            button = ctk.CTkButton(bar, text=text, font=self.font, command=command)
            button.grid(row=0, column=column, padx=(0, 8))
            made.append(button)
        return made

    def buildButtons(self):
        bar = ctk.CTkFrame(self.win, fg_color='transparent')
        bar.grid(row=1, column=0, padx=24, pady=(6, 18), sticky='e')
        self.btnFailed = ctk.CTkButton(bar, text='It failed', width=110, font=self.font,
                                       fg_color=RED, hover_color='#9B1C1C', command=self.failed)
        self.btnFailed.grid(row=0, column=0, padx=(0, 8))
        self.btnNext = ctk.CTkButton(bar, text='Next', width=150, font=self.font, command=self.next)
        self.btnNext.grid(row=0, column=1, padx=(0, 8))
        self.btnCancel = ctk.CTkButton(bar, text='Cancel', width=100, font=self.font,
                                       command=self.close)
        self.btnCancel.grid(row=0, column=2)

    # ---- the pages -------------------------------------------------------------------------

    def pageChoose(self, frame, number):
        self.heading(frame, number, 'Choose the software')
        self.note(frame, 1, 'Choose the release to program: the zip you downloaded from Teams (put it '
                  'in the folder below), a release folder, or a boot_image.sb file.')
        self.folderLabel = self.note(frame, 2, '', GREY)
        bar = ctk.CTkFrame(frame, fg_color='transparent')
        bar.grid(row=3, column=0, sticky='w', pady=(0, 6))
        self.releaseBox = ctk.CTkComboBox(bar, values=[''], width=380, font=self.font,
                                          state='readonly', command=self.pickListed)
        self.releaseBox.grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(bar, text='Browse...', font=self.font, command=self.browse
                      ).grid(row=0, column=1)
        self.pathLabel = self.note(frame, 4, 'No release chosen.', GREY)
        self.releaseLabel = self.note(frame, 5, '')
        self.notes = ctk.CTkTextbox(frame, height=90, width=WRAP, font=self.font, wrap='word')
        self.notes.grid(row=6, column=0, sticky='w', pady=(0, 6))
        self.notes.configure(state='disabled')
        self.toolLabel = self.note(frame, 7, '', RED)
        self.buttonRow(frame, 8, [('Open Configure Paths...', self.onPaths),
                                  ('Check the tool again', self.update)])

    def pageBoard(self, frame, number):
        self.heading(frame, number, 'Prepare the board')
        self.installLabel = self.note(frame, 1, '', GREEN)
        self.steps(frame, number, 2, [
            'Turn off the board (move the power switch to OFF).',
            'Unplug all USB cables to completely remove power from the board.',
            'Insert an SD card into Dubrovnik (if not already in).',
            'Set DIP switch SW5 to OFF-OFF-OFF-OFF (from ON-OFF-ON-OFF).',
            'Plug a micro USB cable into the connector labeled "USB OTG"  (this one first: order matters).',
            'Plug a micro USB cable into the connector labeled "USB UART".'])
        self.note(frame, 8, 'The Terminal may say that the connection was lost when the board is '
                  'switched off. That is expected.', GREY)

    def pageTool(self, frame, number):
        self.heading(frame, number, 'Start the tool and switch the board on')
        self.buttonRow(frame, 1, [('Start MfgTool2', self.startTool)])
        self.toolStartLabel = self.note(frame, 2, '', RED)
        self.steps(frame, number, 3, [
            'MfgTool2 is open.',
            'Turn on the board (move the power switch to ON).',
            'MfgTool2 shows the message "HID-compliant vendor-defined device".'])

    def pageProgram(self, frame, number):
        self.heading(frame, number, 'Program the SD card')
        self.steps(frame, number, 1, [
            'Click Start in MfgTool2 and wait until it has finished.',
            'Note the color of the bars:  GREEN = PASS,  RED = FAIL.',
            'Click Stop in MfgTool2.',
            'Click Exit in MfgTool2.'])
        self.note(frame, 5, 'Was the result GREEN (PASS)?  If yes, click "The bar was green". '
                  'If it was RED (FAIL) or nothing happened, click "It failed".')

    def pageRestart(self, frame, number):
        self.heading(frame, number, 'Restart the board')
        self.steps(frame, number, 1, [
            'Turn off the board.',
            'Unplug the USB cable from the connector labeled "USB OTG".',
            '[Optional] Set DIP switch SW5 to ON-OFF-ON-OFF: the board then starts by itself.',
            'Turn on the board.',
            'If the Terminal says the connection was lost, click Connect in the Serial Connection panel.',
            'Press the RESET button (not needed after the optional SW5 step).'])
        self.note(frame, 7, 'The board prints a start-up message when it restarts. The next page '
                  'reads it from the Terminal.', GREY)

    def pageCheck(self, frame, number):
        self.heading(frame, number, 'Check the software version')
        self.waitLabel = self.note(frame, 1, '')
        self.builtLabel = self.note(frame, 2, '')
        self.verdictLabel = ctk.CTkLabel(frame, text='', font=ctk.CTkFont(size=16, weight='bold'),
                                         anchor='w', justify='left', wraplength=WRAP)
        self.verdictLabel.grid(row=3, column=0, sticky='w', pady=(4, 6))

    # ---- moving between the pages ----------------------------------------------------------

    def show(self, index):
        self.index = index
        self.pages[index].tkraise()
        if index == 4 and self.since is None:
            self.since = self.mark()        # the start-up message after this point counts
        if index == 5:
            self.refreshCheck()
        self.btnNext.configure(text={3: 'The bar was green', 5: 'Finish'}.get(index, 'Next'))
        if index == 3:
            self.btnFailed.grid()
        else:
            self.btnFailed.grid_remove()
        self.update()

    def update(self):
        """Next is available when the page's steps are done (page 1: a file is chosen and the tool
        folder is usable)"""
        if self.index == 0:
            problem = sd_card.tool_problem(self.settings.mfgToolDir)
            self.toolLabel.configure(text=problem or '')
            ready = self.chosen is not None and problem is None
        else:
            ready = all(var.get() for var in self.checks[self.index])
        self.btnNext.configure(state='normal' if ready else 'disabled')
        if self.index == 3:
            self.btnFailed.configure(state='normal' if ready else 'disabled')

    def next(self):
        if self.index == 0 and not self.install():
            return
        if self.index == 5:
            self.log(self.summary())
            self.close()
            return
        self.show(self.index + 1)

    def close(self):
        self.win.destroy()

    # ---- what the pages do -----------------------------------------------------------------

    def releaseFolder(self):
        """Where the releases are: Preferences > Configure Paths > SD card software, or by default
        Documents\\Dubrovnik\\SD-card (made if it is not there)"""
        folder = self.settings.sdImageDir
        if folder and os.path.isdir(folder):
            return folder
        folder = default_folder('SD-card')
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            pass                        # the list is then empty and Browse still works
        return folder

    def fillReleases(self):
        """Lists the releases in the folder, newest first, and chooses the newest"""
        folder = self.releaseFolder()
        self.folderLabel.configure(text=f'Folder: {folder}')
        self.listed = sd_card.find_releases(folder)
        if self.listed:
            self.releaseBox.configure(values=[r.label for r in self.listed])
            self.releaseBox.set(self.listed[0].label)
            self.setRelease(self.listed[0])
        else:
            text = 'No release found in this folder: put the zip from Teams here, or use Browse'
            self.releaseBox.configure(values=[text])
            self.releaseBox.set(text)

    def pickListed(self, label):
        for release in self.listed:
            if release.label == label:
                self.setRelease(release)

    def browse(self):
        """Choose a zip or a boot_image.sb from anywhere (the dialog starts in the releases
        folder; the folder setting is not changed)"""
        path = askopenfilename(
            title='Select the release (zip from Teams, or boot_image.sb)',
            initialdir=self.releaseFolder(),
            filetypes=[('Release', '*.zip *.sb'), ('All files', '*.*')])
        if not path:
            return
        try:
            release = sd_card.open_release(path)
        except sd_card.ReleaseError as e:
            showerror('Program SD Card', f'This cannot be used:\n{path}\n\n{e}', parent=self.win)
            return
        self.releaseBox.set(release.label)
        self.setRelease(release)

    def setRelease(self, release):
        self.chosen = release
        self.release = release.date
        self.pathLabel.configure(text=release.path, text_color=self.textColor)
        if self.release:
            self.releaseLabel.configure(
                text=f'Release date: {self.release:%Y-%m-%d}', text_color=self.textColor)
        else:
            self.releaseLabel.configure(
                text='The name is not a date (yyyymmdd), so the version cannot be checked '
                     'automatically at the end.', text_color=AMBER)
        text = release.notes()
        self.notes.configure(state='normal')
        self.notes.delete('1.0', 'end')
        self.notes.insert('1.0', text if text else 'No release notes (relnotes.docx) with this release.')
        self.notes.configure(state='disabled')
        self.update()

    def install(self):
        """Copies the image of the chosen release into the tool's profile as boot_image.sb; False
        if that failed"""
        try:
            target, backup = self.chosen.install(self.settings.mfgToolDir)
        except (OSError, sd_card.ReleaseError) as e:
            showerror('Program SD Card', f'The file could not be copied:\n{e}', parent=self.win)
            return False
        note = f'{sd_card.IMAGE_NAME} of this release is in place:\n{target}'
        if backup:
            note += f'\n(the one that was there is kept as {os.path.basename(backup)})'
        self.installLabel.configure(text=note)
        return True

    def startTool(self):
        folder = self.settings.mfgToolDir
        try:
            launch(os.path.join(folder, sd_card.TOOL_NAME), folder)
            self.toolStartLabel.configure(text='')
        except OSError as e:
            self.toolStartLabel.configure(text=f'MfgTool2 could not be started: {e}')

    def failed(self):
        showwarning('Program SD Card',
                    'Programming did not work. Things to check:\n\n'
                    '  - the SD card is in and seated\n'
                    '  - DIP switch SW5 is OFF-OFF-OFF-OFF\n'
                    '  - USB OTG was plugged in first, before the board was switched on\n'
                    '  - MfgTool2 said "HID-compliant vendor-defined device"\n\n'
                    'Then start again from Tools > Program SD Card.', parent=self.win)
        self.log('SD card programming failed (MfgTool2 did not show the green bar).')
        self.close()

    def refreshCheck(self):
        text = self.textSince(self.since) if self.since else ''
        self.built = sd_card.banner_time(text)
        self.verdict = sd_card.compare(self.release, self.built)
        if self.built is None:
            self.waitLabel.configure(
                text="Waiting for the board's start-up message ...  Press RESET. The Terminal "
                     'must be connected to the board.', text_color=AMBER)
            self.builtLabel.configure(text='')
            self.verdictLabel.configure(text='')
            return
        self.waitLabel.configure(text='')
        chosen = f'{self.release:%Y-%m-%d}' if self.release else 'not known (the folder name is not a date)'
        self.builtLabel.configure(
            text=f'The board reports software built {self.built:%Y-%m-%d %H:%M:%S}.\n'
                 f'Release chosen: {chosen}.')
        if self.verdict == 'match':
            self.verdictLabel.configure(text='The version is the one you programmed.', text_color=GREEN)
        elif self.verdict == 'differ':
            self.verdictLabel.configure(
                text='The dates are different. Check the release notes: the build date can differ '
                     'from the date of the folder. Programming again may be needed.',
                text_color=RED)
        else:
            self.verdictLabel.configure(text='Compare the two by hand.', text_color=AMBER)

    def summary(self):
        built = f'{self.built:%Y-%m-%d %H:%M:%S}' if self.built else 'no start-up message seen'
        release = f'{self.release:%Y-%m-%d}' if self.release else 'unknown'
        return (f'SD card programmed: release {release}, board reports build {built} '
                f'({self.verdict}).')

    def poll(self):
        """While the last page is shown: look again for the start-up message"""
        if not self.win.winfo_exists():
            return
        if self.index == 5:
            self.refreshCheck()
        self.win.after(POLL_MS, self.poll)
