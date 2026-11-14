"""Python scripts for the Dubrovnik apps (File > Scripts > Run Python Script).

A script is an ordinary Python file. It runs inside the app and gets a ready
made object called ``dub`` for talking to the board:

    dub.send("freq 120")                       # command, returns the reply
    dub.erase(block=4, address=0, blocks=3)    # same as the Erase panel
    dub.program(address=0, length=0x100, pattern="caba0000", increment=1)
    data = dub.read(address=0, length=0x100, mode="Quad (144)")
    raw = dub.read_bytes(0x2000, 0x400)        # the same, as a bytes object
    print(dub.hexdump(raw, 0x2000))            # address / hex / ASCII layout
    image = dub.load_image("fw.srec")          # .bin, S-record or Intel HEX
    dub.program_image(image, offset=0)         # every segment at its address
    bad = dub.verify(0x2000, raw)              # [] when the flash matches
    dub.sleep(0.5)
    name = dub.ask("Device number?", "01")      # dialogs for the user
    path = dub.output_path("results.txt")       # where result files belong

``print()`` writes to the Terminal. The script runs on the GUI thread; every
``dub`` call lets the window update and checks whether the user pressed Esc
(a stop request raises ScriptStopped inside the script).
"""
import contextlib
import os
import sys
import traceback

from dubLibs import firmware_image, hexdump, settings


def documents_dir():
    """The user's Documents folder (also when OneDrive has moved it): the same one the script
    folders of the Preferences start in (settings.documents_folder decides)"""
    return settings.documents_folder()


class ScriptStopped(BaseException):
    """Raised inside a script when the user stops it. It derives from
    BaseException so that a script's own ``except Exception`` can't hide it."""


class ScriptError(Exception):
    """Raised by dub.send() when the board answers with an error"""


class _TerminalWriter:
    """File-like object that sends print() output to the Terminal"""

    def __init__(self, term, check):
        self.term, self.check, self.buf = term, check, ''

    def write(self, text):
        self.buf += text
        while '\n' in self.buf:
            line, self.buf = self.buf.split('\n', 1)
            self.term.scriptPrint(line)
        self.check()
        return len(text)

    def flush(self):
        if self.buf:
            self.term.scriptPrint(self.buf)
            self.buf = ''


class DubApi:
    """The ``dub`` object that Python scripts use to reach the board"""

    def __init__(self, term, du, pump, stopped, ask=None, confirm=None,
                 notify=None, hex_options=None):
        """term: the Terminal widget; du: the Dubrovnik library object;
        pump: function that lets the GUI update; stopped: returns True once
        the user asked to stop the script; ask(prompt, default) -> str or None,
        confirm(question) -> bool and notify(text) show dialogs;
        hex_options() -> the Preferences > Hex View settings for hexdump()"""
        self._term, self.du, self._pump, self._stopped = term, du, pump, stopped
        self._hex_options = hex_options
        self._ask, self._confirm, self._notify = ask, confirm, notify

    # -- housekeeping -----------------------------------------------------
    @property
    def comm(self):
        """The board connection (advanced use)"""
        return self._term.comm

    @property
    def stop_requested(self):
        """True once the user pressed Esc (long loops can poll this)"""
        return self._stopped()

    def _check(self):
        """Lets the GUI update and honours a stop request"""
        self._pump()
        if self._stopped():
            raise ScriptStopped()

    def sleep(self, seconds):
        """Waits, keeping the window alive; Esc interrupts the wait"""
        import time
        end = time.time() + seconds
        while time.time() < end:
            self._check()
            time.sleep(min(0.05, max(0.0, end - time.time())))
        self._check()

    # -- dialogs and files ---------------------------------------------------
    def _dialog(self, function, *args):
        if function is None:
            raise ScriptError('dialogs are not available here')
        self._check()
        result = function(*args)
        self._check()
        return result

    def ask(self, prompt, default=''):
        """Asks the user to type a value; returns the text, or None if the
        dialog was cancelled."""
        return self._dialog(self._ask, prompt, default)

    def confirm(self, question):
        """Yes/No question; returns True for Yes"""
        return bool(self._dialog(self._confirm, question))

    def message(self, text):
        """Shows a message and waits for the user to click OK"""
        self._dialog(self._notify, text)

    def output_path(self, filename):
        """Full path for a result file: Documents\\Dubrovnik\\Results\\filename.
        The folder is created if needed. Use it instead of a bare file name,
        which would end up in whatever folder the program was started from."""
        folder = os.path.join(documents_dir(), 'Dubrovnik', 'Results')
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, filename)

    # -- commands -----------------------------------------------------------
    def send(self, command, check=True, echo=True):
        """Sends one Terminal command and returns the board's reply.
        With check=True (default) an 'Error:' reply raises ScriptError.
        With echo=False the command and reply are not shown in the Terminal."""
        self._check()
        command = command.strip().rstrip(';').strip()
        if echo:
            reply = self._term.runScriptCommand(command)
        else:
            reply = self._term.execute(command)
        self._check()
        if check and reply.strip().lower().startswith('error'):
            raise ScriptError(f'{command}: {reply.strip()}')
        return reply

    def _show(self):
        text = self.du.textToDisplay[:-1]
        if text:
            self._term.scriptPrint(text)

    def erase(self, block=4, address=0, blocks=1):
        """Erases like the Erase panel. block is 4, 32, 64 or 'chip'; address
        is aligned down to the block size. Returns the erase time in us."""
        self._check()
        if block == 'chip':
            self._term.scriptPrint('Erasing chip')
            elapsed = self.du.block_erase(self.comm, 'chip')
        else:
            self._term.scriptPrint(f'Erasing {blocks} {block}kB block(s) '
                                   f'from address {address:x}')
            elapsed = self.du.block_erase(self.comm, block, address, blocks)
        self._show()
        self._check()
        return elapsed

    def program(self, address, length, pattern='cafe0000', increment=1, continuous=False):
        """Programs a pattern like the Program panel. pattern and increment
        may be hex strings or integers. continuous=True keeps the counter
        going across pages (see Dubrovnik.page_program). Returns the program
        time in us."""
        self._check()
        if isinstance(pattern, int):
            pattern = f'{pattern & 0xFFFFFFFF:08x}'
        if isinstance(increment, int):
            increment = f'{increment:x}'
        elapsed = self.du.page_program(self.comm, address, length,
                                       str(pattern), str(increment),
                                       continuous=continuous)
        self._show()
        self._check()
        return elapsed

    def program_bytes(self, address, data):
        """Programs a bytes object at address. Returns the program time in us."""
        self._check()
        elapsed = self.du.data_program(self.comm, data, address)
        self._show()
        self._check()
        return elapsed

    def read(self, address, length, mode='SPI', show=True):
        """Reads like the Read panel; mode is 'SPI', 'Dual', 'Quad (114)' or
        'Quad (144)'. Returns the data as the board prints it (without the
        echoed command line). show=False keeps it out of the Terminal."""
        self._check()
        reply = self.du.read_mode(self.comm, mode, start_addr=address,
                                  length=length, echo=0)
        if show:
            for note in getattr(self.du, 'notes', ()):      # e.g. "(Quad Enable set: ...)"
                self._term.scriptPrint(note)
            self._show()
        self._check()
        cmd = (getattr(self.comm, 'cmdline', '') or '').strip()
        text = reply.lstrip()
        if cmd and text.startswith(cmd):
            text = text[len(cmd):].lstrip('\r\n')
        return text.strip()

    # -- data helpers for script writers ----------------------------------------
    def read_bytes(self, address, length, mode='SPI', chunk=0x1000):
        """Reads like read() but returns a ``bytes`` object of exactly
        ``length`` bytes (nothing is printed). Works whatever the Read panel's
        Display Mode is. Long reads are done in pieces of ``chunk`` bytes, so Esc
        still stops them. Raises ScriptError if the board returns another
        number of bytes than asked for."""
        out = bytearray()
        saved = self.du.dispmode
        self.du.dispmode = 'b'          # the parser needs plain bytes
        try:
            while len(out) < length:
                self._check()
                size = min(chunk, length - len(out))
                start = address + len(out)
                self.du.read_mode(self.comm, mode, start_addr=start,
                                  length=size, echo=0)
                part = hexdump.bytes_from_reply(
                    self.du.textToDisplay, getattr(self.comm, 'cmdline', ''))
                if len(part) != size:
                    raise ScriptError(
                        f'read of {size} bytes at 0x{start:X} returned '
                        f'{len(part)} bytes')
                out.extend(part)
        finally:
            self.du.dispmode = saved
        self._check()
        return bytes(out)

    def hexdump(self, data, address=0, **options):
        """Text dump of ``data`` like a hex editor: address, hex bytes, ASCII.
        Uses the layout chosen in Preferences > Hex View; options override it for this
        call: per_row (8, 16 or 32), show_ascii, upper, gap (True/False)."""
        layout = dict(self._hex_options()) if self._hex_options else {}
        layout.update(options)
        return hexdump.format_hexdump(bytes(data), address, **layout)

    def load_image(self, path):
        """Reads a .bin, S-record or Intel HEX file (format recognised from its
        content) and returns the image: ``image.segments`` is a list of
        ``(address, bytes)``, ``image.size``, ``image.start``, ``image.end``.
        Raises ScriptError for a missing or invalid file."""
        self._check()
        try:
            return firmware_image.load_image(path)
        except OSError as e:
            raise ScriptError(f'{path}: {e}') from None
        except firmware_image.ImageError as e:
            raise ScriptError(f'{path}: {e}') from None

    def program_image(self, image, offset=0):
        """Programs every segment of an image (or of the file at that path) at
        its address plus ``offset``; the gaps between segments are not touched.
        Nothing is erased first. Returns the total programming time in us."""
        if isinstance(image, (str, os.PathLike)):
            image = self.load_image(image)
        total = 0
        for address, data in image.segments:
            total += self.program_bytes(address + offset, data)
        return total

    def verify(self, address, data, mode='SPI', limit=32):
        """Compares the flash at ``address`` with ``data`` (bytes). Returns a
        list of ``(address, expected, actual)`` for the first ``limit``
        differing bytes; an empty list means the flash matches."""
        data = bytes(data)
        actual = self.read_bytes(address, len(data), mode)
        bad = []
        for offset, (want, got) in enumerate(zip(data, actual)):
            if want != got:
                bad.append((address + offset, want, got))
                if len(bad) >= limit:
                    break
        return bad


def run_file(path, api, term):
    """Runs the Python file at path with ``dub`` available.
    Returns (ok, message): ok is True on normal completion; otherwise message
    says why the script stopped (user stop, error with line number, ...)."""
    try:
        with open(path, encoding='utf-8-sig') as fh:
            source = fh.read()
        code = compile(source, path, 'exec')
    except (OSError, UnicodeDecodeError) as e:
        return False, f'could not read the file: {e}'
    except SyntaxError as e:
        return False, f'syntax error at line {e.lineno}: {e.msg}'
    namespace = {'__name__': '__main__', '__file__': path, 'dub': api}
    out = _TerminalWriter(term, api._check)
    folder = os.path.dirname(os.path.abspath(path))
    sys.path.insert(0, folder)      # lets the script import modules next to it
    try:
        with contextlib.redirect_stdout(out):
            exec(code, namespace)
        out.flush()
        return True, ''
    except ScriptStopped:
        out.flush()
        return False, 'stopped by the user'
    except SystemExit:
        out.flush()
        return True, ''
    except Exception as e:
        out.flush()
        line = None
        for frame in traceback.extract_tb(e.__traceback__):
            if frame.filename == path:
                line = frame.lineno
        where = f'line {line}: ' if line else ''
        return False, f'{where}{type(e).__name__}: {e}'
    finally:
        if folder in sys.path:
            sys.path.remove(folder)
