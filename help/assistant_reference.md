# Dubrovnik Workbench: reference for writing scripts

This file is written for an AI model (the Workbench Assistant) that turns a test engineer's plain-language
request into a Python script. A human can use it as a cheat sheet too. Read all of it before writing a script.
Every claim here comes from the Workbench source or its user guide. Where something is not known it says so:
**ask the user instead of guessing.**

## 1. What you are writing

- **The board.** Dubrovnik is an SPI flash test board. The PC talks to it over a serial port. The firmware is
  called Tiberias. The user types text commands such as `freq 120` or `9f 3`, or uses the Workbench buttons.
- **The script.** A script is one ordinary Python file (Python 3, standard library only). The Workbench runs it
  and provides a ready-made object called `dub`. There is nothing to import for it, and the script must not
  open a serial port itself.
- **Output and stopping.** `print()` writes to the Workbench Terminal. The user can stop a script with Esc;
  it stops at the next `dub` call or `print`.
- **No console input.** `input()` does not work. Use `dub.ask()` and `dub.confirm()`.
- **No blocking sleep.** `time.sleep()` freezes the window. Use `dub.sleep(seconds)`.
- **No outside packages.** Do not use numpy, pandas, pyserial or anything else that is not in the standard library.
- **Safety.** A script runs on real hardware. A wrong script can erase a device or put a wrong voltage on it.
  The user reviews every script before it runs, but write it so the review is easy: short, commented, with
  the settings at the top.

## 2. The `dub` object

Times are in microseconds. Addresses and lengths are Python integers (write them as `0x1000`).

| Call | What it does |
|---|---|
| `dub.send(command, check=True, echo=True)` | Sends one Terminal command, returns the board's reply as text. An `Error:` reply raises `ScriptError` and stops the script unless `check=False`. `echo=False` keeps the command and reply out of the Terminal. A trailing `;` is removed. |
| `dub.erase(block=4, address=0, blocks=1)` | Same as the Erase panel. `block` is `4`, `32`, `64` (kB) or `'chip'`. The address is rounded down to the block size, and `blocks` blocks from there are erased. With `'chip'` the address and count are ignored. Returns the time. |
| `dub.program(address, length, pattern='cafe0000', increment=1)` | Programs a 32-bit pattern, as the Program panel does. `pattern` is 8 hex digits (a string) or an int. `increment` is added to the pattern for each following word (hex string or int, may be negative). `length` is in bytes. Returns the time. **It does not erase first.** |
| `dub.program_bytes(address, data)` | Programs a `bytes` object. Not erased first. Returns the time. |
| `dub.read(address, length, mode='SPI', show=True)` | Same as the Read panel. `mode` is `'SPI'`, `'Dual'`, `'Quad (114)'` or `'Quad (144)'`. Returns the data as text. `show=False` keeps it out of the Terminal. |
| `dub.read_bytes(address, length, mode='SPI')` | Like `read`, but returns a `bytes` object of exactly `length` bytes and prints nothing. Use this when the script needs the data. |
| `dub.verify(address, data, mode='SPI', limit=32)` | Compares the flash with `data` (bytes). Returns a list of `(address, expected, actual)` for the first `limit` differences. An empty list means the flash matches. |
| `dub.load_image(path)` | Reads a `.bin`, S-record or Intel HEX file. Returns an image: `image.segments` is a list of `(address, bytes)`; also `image.size`, `image.start`, `image.end` (`end` is the address after the last byte). A bad file raises `ScriptError`. |
| `dub.program_image(image, offset=0)` | Programs every segment at its address plus `offset`. Accepts a path as well. Gaps are untouched and **nothing is erased first.** |
| `dub.hexdump(data, address=0)` | Returns a text dump (address, hex, ASCII). Use `print(dub.hexdump(...))`. |
| `dub.sleep(seconds)` | Waits and keeps the window alive. |
| `dub.stop_requested` | `True` after the user pressed Esc. A long loop can check it. |
| `dub.ask(prompt, default='')` | Asks for text. Returns the text, or `None` if the user cancelled. Always handle `None` (see the examples). |
| `dub.confirm(question)` | Yes/No dialog. Returns `True` for Yes. |
| `dub.message(text)` | Shows a message and waits for OK. |
| `dub.output_path(filename)` | Full path of a result file in `Documents\Dubrovnik\Results`. Always use it for files you write. |
| `dub.comm`, `dub.du` | The raw connection and the library object, for advanced use only (`dub.du.get_config(dub.comm)` returns a dict with keys such as `'Part#'`, `'Voltage'`, `'Frequency'`, `'min meas time (us)'`). Prefer `dub.send`. |

Not on this list means it does not exist. Do not invent methods such as `dub.set_voltage()` or `dub.read_id()`.
For anything not covered, use `dub.send('<board command>')`.

## 3. Board commands for `dub.send`

Commands are not case sensitive. Several commands can be chained on one line with `;`. The board then runs
them back to back, which is what you want for timing and power measurements. Text after `#` is a comment and
is not sent.

**Number formats.** This is the most common mistake.
- Flash opcodes, their addresses and data, and the buffer commands (`pattern`, `write`, `dump`, `cmp`) are **hexadecimal without `0x`**.
- `freq` (MHz), `volt` and `psset` (volts), `delay` (µs), `dummy` (cycles) and GPIO pin numbers are **decimal**.

A command that starts with a hexadecimal number is a flash opcode: `opcode [address] [count or data]`.

| Command | Meaning |
|---|---|
| `ver`, `config` | Firmware version. Part number, voltage, clock, dummy cycles and power monitor settings. |
| `freq 120` | SPI clock in MHz. The board uses the closest value it can make and prints it. |
| `volt 1.8` | Voltage of the device socket, in volts. |
| `psset 0 1.8`, `psget 0` | Set and read a supply domain's voltage. |
| `dispmode b` / `dispmode w` | Show read data as bytes or as 32-bit words. |
| `echo off` / `echo on` | Hide or show the data of reads. Use `echo off` for timing and power. If a script leaves it off, reads show no data until `echo on`. |
| `delay 50000` | Wait 50 ms (the value is in µs). |
| `timer start` / `timer stop`, then `dvar elapsed_time` | Measure the time between the two. |
| `wait 0`, then `dvar wait_time` | Wait until the device has finished an erase or program. `dvar wait_time` shows how long it took. |
| `9f 3` | Flash opcode 9F: read the JEDEC ID (manufacturer, device ID). |
| `05`, `35`, `15` | Read status register 1, 2, 3. |
| `06` | Write enable. **It must come before every erase and program.** |
| `06; 20 1000; wait 0` | Write enable, erase the 4 kB block at 0x1000, wait until done. (`52` erases 32 kB, `d8` 64 kB, `60` the chip.) |
| `pattern caba0000 1` | Fill the 16 KB write buffer with 32-bit words, each larger by the second number. |
| `write 0 abcdef` | Put up to 16 bytes into the write buffer at an offset. |
| `06; 2 3000 100; wait 0` | Program 0x100 bytes at 0x3000 from the write buffer. |
| `0b 3000 100` | Read 0x100 bytes from 0x3000 into the read buffer (fast read). |
| `dump r 0 40`, `dump w 0 40` | Show the read / write buffer. |
| `cmp 0 100` | Compare the read buffer with the write buffer; prints `Equal!` or the differences. |
| `jrst`, `hwrst` | Reset the flash (JEDEC reset, or with the reset pin). |
| `gpiocfg 7 o`, `gpiowr 7 1`, `gpiord 15` | GPIO: configure a pin (`i` or `o`), write, read. Pin 7 is the scope trigger pin. |
| `help all`, `help <command>` | List the board commands, or show one command's syntax. |

Reads with more data lines: `3b` Dual, `6b` Quad (1-1-4), `eb <addr> <mode> <count>` Quad I/O (1-4-4).
**Quad reads need the Quad Enable bit (QE) = 1 in status register 2.** On many devices that is set with
`06; 31 2` (clear it with `06; 31 0`). This differs between devices, so ask the user if the device is unknown.
`dub.read(..., mode='Quad (144)')` handles it as the Read panel does.

**Power measurement.** The device socket is power domain 5 (the BGA socket is domain 0).
Remove the domain's jumper first, or the reading is 0 V (tell the user in a `dub.message`).

```
pmoncfg meas iv                               # what "calc" prints: i, v, p or iv
pmon 5 start; 0b 0 1000; pmon 5 stop; pmon 5 calc
```

Put the operation between `pmon 5 start` and `pmon 5 stop` **on one line**. The monitor needs a finished
conversion: an event shorter than `config`'s `min meas time (us)` (9344 µs by default) gives `Error: 0 samples
collected`. Make the event longer, or faster monitor settings with `pmoncfg vst 1100`, `pmoncfg mode svc`.
The reply of `pmon ... calc` is text; the existing tool `tools/functional_test.py` shows how to pick the
numbers out of it (`reply.splitlines()[0].split(' ')`, current at index 2 and voltage at index 6 when
`meas iv`). Check the reply before relying on that layout.

## 4. Rules for a good script

1. **Settings first.** Put the values the user may want to change (addresses, voltage, frequency, file
   names) as named constants at the top.
2. **Ask before anything destructive.** Before an erase, a program, a voltage or clock change, call
   `dub.confirm('...')`, say what will change, and `raise SystemExit` if the answer is No.
3. **Erase before program.** Flash can only be programmed where it is erased. `dub.program`,
   `dub.program_bytes` and `dub.program_image` never erase. Erase blocks of 4, 32 or 64 kB that cover the
   whole range, aligned down to the block size.
4. **Verify what you program** with `dub.verify(...)` or the `cmp` command, and print a clear PASS or FAIL.
5. **Voltage and frequency limits.** Never set a voltage above what the user states. If the limit is not
   given, ask. A script that exists in the repository uses `float(config['Voltage']) + 0.3` as the absolute
   maximum. Do not copy that number as a safe value for a new device; ask.
6. **Keep long loops stoppable.** Use `dub.sleep()`, and check `dub.stop_requested` in loops that take more
   than a few seconds.
7. **Files.** Write result files only through `dub.output_path('name.txt')`, and close them (use `with`).
8. **Say what happens.** `print()` a short line for each step. The user watches the Terminal.
9. **Keep it simple.** Prefer `dub.erase`, `dub.program`, `dub.read_bytes` and `dub.verify` over raw commands.
   Use `dub.send` for what they do not cover.
10. **Do not guess.** If you do not know a command's syntax, a device's register layout or a limit, say so and ask. You
    can suggest the user type `help <command>` in the Terminal.

## 5. Examples

### 5.1 Read the JEDEC ID and the status registers

```python
print('JEDEC ID  :', dub.send('9f 3', echo=False).strip())
print('Status 1  :', dub.send('05', echo=False).strip())
print('Status 2  :', dub.send('35', echo=False).strip())
```

### 5.2 Erase, program a pattern, verify with the board's compare

```python
ADDRESS = 0x3000        # start (4 kB aligned)
LENGTH = 0x100          # bytes
PATTERN = 'caba0000'    # 8 hex digits
STEP = 1                # added to the pattern for each 32-bit word

if not dub.confirm(f'Erase the 4 kB block at 0x{ADDRESS:X} and program 0x{LENGTH:X} bytes there?'):
    raise SystemExit

dub.erase(block=4, address=ADDRESS, blocks=1)
dub.send(f'pattern {PATTERN} {STEP:x}', echo=False)         # fills the write buffer
dub.send(f'06; 2 {ADDRESS:x} {LENGTH:x}; wait 0', echo=False)  # page program from the write buffer
dub.send(f'0b {ADDRESS:x} {LENGTH:x}', echo=False)           # read back into the read buffer
reply = dub.send(f'cmp 0 {LENGTH:x}', echo=False)
print('PASS' if 'Equal' in reply else 'FAIL')
print(reply)
```

### 5.3 Program a firmware file and verify it

```python
path = dub.ask('Firmware file (.bin, .srec, .hex):', '')
if not path:
    raise SystemExit
image = dub.load_image(path)
OFFSET = 0
BLOCK = 4                                       # kB
size = BLOCK * 1024
first = (image.start + OFFSET) // size * size
count = (image.end + OFFSET - first + size - 1) // size
if not dub.confirm(f'Erase {count} block(s) of {BLOCK} kB from 0x{first:X} and program {image.size} bytes?'):
    raise SystemExit

dub.erase(block=BLOCK, address=first, blocks=count)
dub.program_image(image, offset=OFFSET)
bad = []
for address, data in image.segments:
    bad += dub.verify(address + OFFSET, data)
print('PASS' if not bad else f'FAIL: {len(bad)} differing byte(s), first at 0x{bad[0][0]:X}')
```

### 5.4 Read a region and show it as a hex dump

```python
ADDRESS, LENGTH = 0x0, 0x100
data = dub.read_bytes(ADDRESS, LENGTH, mode='SPI')
print(dub.hexdump(data, ADDRESS))
```

### 5.5 Read the same region at several clock frequencies and compare

```python
ADDRESS, LENGTH = 0x0, 0x400
FREQS = [8, 30, 60, 120]                    # MHz

reference = dub.read_bytes(ADDRESS, LENGTH)
for f in FREQS:
    if dub.stop_requested:
        break
    dub.send(f'freq {f}', echo=False)
    data = dub.read_bytes(ADDRESS, LENGTH)
    print(f'{f:4d} MHz:', 'same as reference' if data == reference else 'DIFFERENT')
dub.send('freq 8', echo=False)              # leave the board at a safe, slow clock
```

### 5.6 Ask the user for values, keep a result file

```python
unit = dub.ask('Unit number:', '01')
if unit is None:                             # the user pressed Cancel
    raise SystemExit

id_text = dub.send('9f 3', echo=False).strip()
with open(dub.output_path(f'unit_{unit}_id.txt'), 'w') as f:
    f.write(f'Unit {unit}\n{id_text}\n')
print('Saved unit_%s_id.txt in Documents\\Dubrovnik\\Results' % unit)
```

### 5.7 Current of a read (power domain 5)

```python
dub.message('Remove the jumper J16 of the device supply, then click OK.')
dub.send('echo off', echo=False)
dub.send('pmoncfg meas iv', echo=False)
reply = dub.send('pmon 5 start; 0b 0 4000; pmon 5 stop; pmon 5 calc', echo=False, check=False)
dub.send('echo on', echo=False)
print(reply.strip())                        # a read of 0x4000 bytes is long enough in SPI mode
```

### 5.8 A command script that appears in the Tools menu

A plain text file (`.txt` or `.scr`) in the `tools` folder whose **first line** is `# TOOL: name` is listed in
the Tools menu. One Terminal command per line; `#` starts a comment.

```
# TOOL: Basic device check
# a quick look at the device in the socket
config
9f 3            # JEDEC ID
05              # status register 1
35              # status register 2
```

## 6. Before you propose a script, check

- Every `dub.` call is in section 2, with the arguments in the right order.
- Hex values in `dub.send` strings have no `0x` and use `:x` formatting for numbers.
- A program is preceded by an erase of the same range, and followed by a verify.
- Anything destructive is behind `dub.confirm`.
- There is no `input()`, no `time.sleep()`, no `import serial`, no file written outside `dub.output_path`.
- Voltage and clock stay inside the limits the user gave.
- The summary says exactly what the script changes on the board.
