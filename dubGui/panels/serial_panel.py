"""The Serial Connection panel: choose the COM port, connect to the board and notice
when the board is switched off."""
from tkinter import E, EW, IntVar
from tkinter import ttk
from tkinter.messagebox import showerror, showinfo, showwarning
import customtkinter as ctk
from dubGui.look import CHECKBOX_STYLE
from dubGui.panels.base import LabeledFrame
from dubLibs.boardcom import BoardTimeout, TIMEOUT_LIST


class SerComFrame(LabeledFrame):
    def __init__(self, parent, settings, du, term, statusLabel, scriptStop, DEBUG=False):
        LabeledFrame.__init__(self, parent, text='Serial Connection')
        self.settings = settings              # the remembered settings (dubLibs/settings.py)
        self.du = du                          # the board library object
        self.term = term                      # the Terminal: messages about the connection
        self.statusLabel = statusLabel        # the status bar of the main window
        self.scriptStop = scriptStop          # [bool]: set True to stop a running script
        self.DEBUG = DEBUG
        self.STANDALONE = False
        self.comm = None                      # object created by boardcom
        self.portStatus = 'disconnected'
        self.portList = []
        self.portHandle = None
        self.chk_var = IntVar()
        self.serParams = ''
        self.scriptRunning = False   # True while File > Run Script is running

        self.buildFrame()

    def buildFrame(self):
        '''Makes a reusable frame for a connecting to Dubrovnik board'''
        chk = ctk.CTkCheckBox(self, **CHECKBOX_STYLE, text='Auto connect', variable=self.chk_var)
        chk.grid(row=1, column=0, padx=10, pady=4)

        # ttk.Combobox kept here because CTkComboBox has no `postcommand`
        # (refresh-on-open) equivalent. Aesthetic gap is minor.
        # Same font as the CTk widgets next to it (their default font, scaled
        # the way CTk scales it, so the size matches at every Windows scaling).
        comboFont = ctk.CTkFont().create_scaled_tuple(self._get_widget_scaling())
        self.combo = ttk.Combobox(
            self, width=8, values=self.portList, font=comboFont,
            postcommand=self.updtPortList)
        self.option_add('*TCombobox*Listbox.font', comboFont)
        self.combo.grid(row=1, column=1, padx=10, pady=4)

        self.btn2 = ctk.CTkButton(self, text='Connect', width=100,
                                  command=self.connectPort)
        # Right-aligned: the panel is stretched to the Erase panel's width, and
        # the button's right edge then lines up with the Erase button's.
        self.btn2.grid(row=1, column=2, padx=10, pady=4, sticky=E)
        self.grid_columnconfigure(2, weight=1)

        if self.STANDALONE:
            self.btn3 = ctk.CTkButton(self, text='Save Config', width=100,
                                      command=self.settings.save)
            self.btn3.grid(row=1, column=3, padx=10, pady=4, sticky=E)

        if self.DEBUG:
            self.test_btn = ctk.CTkButton(self, text='Testing', width=100,
                                          command=self.testSerComm)
            self.test_btn.grid(row=2, column=0, padx=5, pady=10, columnspan=1)
            self.test_lbl = ctk.CTkLabel(
                self, text="Debug message:", anchor='w')
            self.test_lbl.grid(row=2, column=1, padx=5,
                               pady=10, sticky=EW, columnspan=3)

    def updtPortList(self):
        self.portList = self.comm.findPorts(exit_if_none=False)
        self.combo['values'] = self.portList
        if self.portList:
            self.combo.set(self.portList[0])
        elif self.portStatus == 'disconnected':
            self.combo.set('')
            self.statusLabel.configure(text='No COM port found: connect the USB cable, '
                             'turn on the board and press RESET')

    def connectPort(self, defaultPort=None, checkIsFlashPresent=True):
        if self.scriptBusy():
            return
        if self.portStatus == 'disconnected':
            if defaultPort:
                self.selPort = defaultPort         # updates class variable as well
                self.combo.set(self.selPort)
            else:
                self.selPort = self.combo.get()
            if not self.selPort:            # nothing chosen yet: look again
                self.updtPortList()
                self.selPort = self.combo.get()
            if not self.selPort:
                showwarning(
            'No board found',
            'No Dubrovnik board was found.\n\n1. Connect the USB cable\n'
            '2. Turn on the board\n3. Press the RESET button\n\n'
            'Then click Connect (the COM port list refreshes when you open it).')
                return
            # only if disconnected, connect to selected port
            self.portHandle = self.comm.connect(self.selPort)
            if self.portHandle is None:     # the port could not be opened
                self.statusLabel.configure(text=f'Could not open {self.selPort}')
                return
            self.setSerialParams()
            self.btn2.configure(text='Disconnect')  # change button label
            self.portStatus = 'connected'  # update connection status
            self.serParams = f'Connected: {self.comPort} ({self.comBaudrate},{self.comBytesize},{self.comParity},{self.comStopbits},{self.comXonXoff})'
            self.statusLabel.configure(text=self.serParams)   # connected, whatever the board says
            if checkIsFlashPresent:  # allow this part to run only when enabled by func argument
                self.comm.retryDialog = False       # a silent board gets a message, not a loop
                try:
                    if self.comm.isFlashPresent():
                        pn = self.du.get_part_number(self.comm)
                        self.serParams += '    Device: ' + pn
                        self.statusLabel.configure(text=self.serParams)
                except BoardTimeout as e:
                    self.term.displayText('*** ' + str(e) + ' ***')
                    showwarning("Board not responding", TIMEOUT_LIST)
                finally:
                    self.comm.retryDialog = True

        elif self.portStatus == 'connected':
            # if connected, disconnect from the current port
            self.disconnectPort(self.selPort)
            self.btn2.configure(text='Connect')  # update button label
            self.portStatus = 'disconnected'  # update connection status
            self.statusLabel.configure(text='Disconnected')
        else:
            print('No such port. Try again!!!')
        self.settings.save()

    def disconnectPort(self, selPort):
        self.comm.disconnect(selPort)
        self.statusLabel.configure(text='No COM port found!')

    def scriptBusy(self):
        """True (with a message) while a script is running: the panels, the
        connection button and the Terminal command line are blocked meanwhile"""
        if self.scriptRunning:
            showinfo('Script', 'A script is running.\nPress Esc or choose '
                     'File > Stop Script to stop it.')
        return self.scriptRunning

    def checkConnection(self):
        """True if connected; otherwise shows a message and returns False"""
        if self.portStatus == 'disconnected':
            showerror('Dubrovnik Workbench Error',
                      'Unable to open COM port!\nConnect to the board')
            return False
        return True

    def connectionLost(self):
        """The board was switched off or unplugged: its COM port is gone.
        Closes the port and brings the window back to the disconnected state."""
        if self.portStatus != 'connected':
            return
        lost = self.selPort
        try:
            self.comm.disconnect(lost, echo=0)
        except Exception:
            pass                        # the port is gone anyway
        self.portStatus = 'disconnected'
        self.serParams = ''
        self.btn2.configure(text='Connect')
        self.statusLabel.configure(text=f'Connection to {lost} lost: the board was '
                         'switched off or unplugged')
        self.term.displayText(f'*** Connection to {lost} lost (board switched off or '
                         'unplugged). Switch it on, press RESET and click '
                         'Connect. ***')
        if self.scriptRunning:          # a script can't go on without the board
            self.scriptStop[0] = True

    def deviceDetected(self, partNumber):
        """The board (re)detected its device, e.g. after being switched off and
        on again: show it in the status bar ('' = no device)"""
        if self.portStatus != 'connected':
            return
        base = self.serParams.split('    Device:')[0]
        self.serParams = base + (f'    Device: {partNumber}' if partNumber else '')
        self.statusLabel.configure(text=self.serParams)

    def checkLink(self):
        """Every 2 s: is the COM port of the connected board still there?
        (Backs up the faster check in Terminal.pollSerial.)"""
        if self.portStatus == 'connected':
            try:
                present = self.selPort in self.comm.getPortList()
            except Exception:
                present = True          # can't tell: assume it is
            if not present:
                self.connectionLost()
        self.after(2000, self.checkLink)

    def setSerialParams(self):
        """ Gets serial communication port parameters """
        self.comPort = self.portHandle.port
        self.comBaudrate = self.portHandle.baudrate
        self.comBytesize = self.portHandle.bytesize
        self.comParity = self.portHandle.parity
        self.comStopbits = self.portHandle.stopbits
        self.comXonXoff = self.portHandle.xonxoff

    @property
    def selPort(self):
        """The port chosen last. It is also what is remembered as lastUsedPort"""
        return self.settings.lastUsedPort

    @selPort.setter
    def selPort(self, value):
        self.settings.lastUsedPort = value

    def autoConnectChanged(self, *_args):
        """The Auto connect check box was clicked: remember it at once"""
        self.settings.autoConnect = self.chk_var.get()
        self.settings.save()

    def testSerComm(self):
        serParams = '%s, baud=%d, bytes=%1d,\nparity=%s, stop=%1d, protocol=%s' \
            % (self.comPort, self.comBaudrate, self.comBytesize, self.comParity, self.comStopbits, self.comXonXoff)
        self.test_lbl.configure(text=serParams)
