import re
from dubLibs import boardcom

# Chip erase times measured on the board (programmed cells take a little longer), by
# JEDEC ID (manufacturer, type, capacity byte). Add a line when you measure a device.
MEASURED_ERASE_S = {
    (0x1F, 0x84, 0x01): 1.388,      # AT25SF041B   512 kB
    (0x1F, 0x47, 0x0C): 59.376,     # AT25XE321D   4 MB
    (0x1F, 0x42, 0x18): 83.7,       # AT25SL128A   16 MB
}
# Other devices: a power law through the AT25SF041B and AT25SL128A points. Devices differ a
# lot (the AT25XE321D is 3.7 times slower than this), so the estimate is a rough guess.
ERASE_REF_BYTES = 512 * 1024
ERASE_REF_S = 1.388
ERASE_EXPONENT = 1.183
CHIP_ERASE_DEFAULT_S = 60       # when the capacity of the device is not known


class Dubrovnik:
    def __init__(self):
        self.pageSize = 0x100
        self.wel = '06'
        self.stsForms = None        # (comm, commands) of status_forms()
        self.led_dict = {'r1': '9', 'g1': '11', 'b1': '10',
                         'r2': '14', 'g2': '13', 'b2': '12'}
        # used by other modules to display text(e.g. the Workbench)
        self.textToDisplay = ""
        self.dispmode = 'b'

    def get_version(self, comm, echo=1):
        """### Returns Tiberias software version"""
        comm.send('ver')
        resp = comm.response(removeCmd=True, removePrompt=True)
        if echo:
            print(resp)
        return resp

    def set_dispmode(self, comm, mode='b'):
        """### Configures how data is displayed in the console
        Parameters:\n
        * comm : Handle to comm port to communicate with the Dubrovnik board
        * mode : binary ('b'), double-word ('w') or hex dump ('h')
          ('h' is formatted on the PC from binary data, see hexdump.py, so the
          board is set to binary mode)
        """
        comm.send(f'dispmode {"b" if mode == "h" else mode}')
        self.dispmode = mode

    def global_echo(self, comm, onoff):
        """### Turns global echo on/off
        Parameters:
        * comm  : Handle to comm port to communicate with the Dubrovnik board
        * onoff : 'on' or 'off' to set global echo\n
        No return value
        """
        if onoff.lower() in ['on', 'off']:
            comm.send(f'echo {onoff}')
        else:
            print('Echo variable onoff must be "on" or "off".')
        return None

    def update_byte(self, old_byte, mask, data):
        new_byte = (old_byte & ~mask) | (data & mask)
        return new_byte

    def tohex(self, num):
        """
        Takes an integer and returns the hex string representation of 
        the least significant byte (with leading zeros)
        Parameters:   
            num : unsigned integer value to change to string (1 byte)
        Examples:
            print(tohex(0x3)
            out: '03'
        """
        if type(num) is int:
            bs = format(num, "02x")
        elif type(num) is str:
            if 'x' in num:
                bs = num.split('x')[-1]
            else:
                bs = num
        else:
            try:
                bs = format(int(num), "02x")
            except Exception:
                bs = format(int(num, 16), "02x")
        return bs

    def get_wait_time_us(self, comm):
        """### Gets and returns the wait time for certain operations to finish
        Prerequisit: previously a 'wait 0' or 'wait 1' command must be issued\n
        The 'wait 0/1' command polls the RDY#/BUSY bit. Tiberias measures and stores the time
        the bit was set to specified value (0 or 1). It calculates and returns this time using
        the 'dvar wait_time' command.
        Returns: wait (elapsed) time (int) in microseconds [us]
        """
        comm.send('dvar wait_time')  # returns a list: ['[time_val] us']
        resp = comm.response(removeCmd=True, removePrompt=True,
                             returnAsList=True)[0]
        # strips off 'us', converts to int
        wait_time_us = int(resp.split(' ')[0])
        return wait_time_us

    def time_conv_from_usec(self, elapsed_time):
        """Converts time expressed in microseconds to a more human readable format\n
        Returns a value converted into us, ms or sec depending on the magnitude.
        """
        if elapsed_time < 1e3:
            wait_time = f'{elapsed_time} us'
        elif elapsed_time >= 1e3 and elapsed_time < 1e6:
            wait_time = f'{elapsed_time/1e3:.3f} ms'
        else:
            wait_time = f'{elapsed_time/1e6:.3f} sec'
        return wait_time

    def get_config(self, comm):
        """Sends config command, parses it and returns
        a dictionary with config parameters"""
        config_dict = {}
        comm.send('config')
        config = comm.response(
            removeCmd=True, removePrompt=True, returnAsList=True)
        for item in config:
            conf = item.split('=')
            key = conf[0].strip()
            if 'PMON conf' in key:
                continue  # skip "PMON configuration" subtitle
            val = conf[1].strip()
            config_dict[key] = val
        return config_dict

    def set_host_dummy_cycles(self, comm, num_dummy=4):
        comm.send(f'dummy {num_dummy}')

    def set_flash_dummy_cycles(self, comm, num_dummy=4):
        pass

    def get_part_number(self, comm):
        """Returns the part number of the detected device"""
        self.forget_status_forms()      # asked at connect and when the device is detected again
        cfg = self.get_config(comm)  # returns a dictionary
        return cfg['Part#']

    # TODO: instad of providing the opcode, should we have separate read commands for each read types?
    # read_0b or fast_read
    # read_03 or legacy_read
    # read_114
    # read_144
    # read_444
    # read_888

    def read(self, comm, start_addr=0, length=256, echo=1, opcode='0b',
             mode_byte=None):
        """### Reads content of flash memory
        Parameters:\n
        * comm       : handle to comm port to communicate with the Dubrovnik board
        * start_addr : start reading from this address
        * length     : the number of bytes to read
        * echo       : if 1, it will print the respose to the console
        * opcode     : defines which opcode to use for read e.g. '03', '0b'
        * mode_byte  : hex mode byte for opcodes that take one between address
                       and count, e.g. 'eb' (<addr> <mode> <count>); else None
        Returns the response string from Tiberias
        """
        self.textToDisplay = ""
        # CM use class attribute instead of passing it in the argument
        self.set_dispmode(comm, self.dispmode)
        if mode_byte is None:
            cmdstr = f'{opcode} {start_addr:x} {length:x}'
        else:
            cmdstr = f'{opcode} {start_addr:x} {mode_byte} {length:x}'
        comm.send(cmdstr)
        resp = comm.response()
        self.textToDisplay = resp
        if echo:
            print(resp)
        return resp

    def read_id(self, comm, opcode='9f ', narg=2, echo=1):
        self.textToDisplay = ""
        cmdstr = f'{opcode} {str(narg)}'
        comm.send(cmdstr)
        resp = comm.response()
        self.textToDisplay = resp
        if echo:
            print(resp)
        return resp

    def file_loader(self, datafile):
        """### Opens and loads a file
        * opens filename specified by file name: datafile
        * reads it into a binary array
        * returns the binary array
        """
        try:
            fh = open(datafile, 'rb')
        except FileNotFoundError:
            print("Error: file", datafile, "not found")
            exit()

        data_array = fh.read()
        return data_array

    def srec_file_loader(self, srec_filename):
        """### Opens and loads an srec file
        * opens srec_filename
        * reads it line by line
        * processes data lines which start with S1, S2, S3
        * finds gaps in the data a essentially breaking it to
        * a list of contiguous blocks
        * returns:
        * 1. a list of start addresses, one per contiguous block
        * 2. a list of matching binary arrays, holding the data
        * for each contiguous block
        """
        try:
            fh = open(srec_filename, 'r')
        except FileNotFoundError:
            print("Error: file", srec_filename, "not found")
            exit()
        addr_list = []
        block_list = []
        next_addr = 0
        for line in fh:
            if line[:2] == "S1":
                nbytes = (int(line[2:4], 16) - 3)
                addr = int(line[4:8], 16)
                data_start = 8
            elif line[:2] == "S2":
                nbytes = (int(line[2:4], 16) - 4)
                addr = int(line[4:10], 16)
                data_start = 10
            elif line[:2] == "S3":
                nbytes = (int(line[2:4], 16) - 5)
                addr = int(line[4:12], 16)
                data_start = 12
            else:
                continue

            if addr > next_addr or addr == 0:
                block_list.append(b"")
                addr_list.append(addr)

            next_addr = addr + nbytes
            block_list[-1] += bytes.fromhex(
                line[data_start:data_start+(nbytes*2)])
        return (addr_list, block_list)

    def write_buf_write(self, comm, inp_arr, dsize, progress=None):
        """
        * takes an input binary array
        * loads the data from the binary array into the
        * Tiberias write buffer using a sequence of 'write' commands
        * progress(bytes_done), if given, is called after each 'write' command
          (it may raise an exception to abort)
        """
        offst = 0
        while offst < dsize:
            if dsize - offst >= 16:
                end_offst = offst + 16
            else:
                end_offst = dsize
            cmdstr = f'write {offst:x} '
            while offst < end_offst:
                cmdstr += f'{inp_arr[offst]:02x}'
                offst += 1
            comm.send(cmdstr)
            if progress:
                progress(offst)

    def data_program(self, comm, data_array, start_addr=0, progress=None):
        """
        * gets a binary data array from the caller
        * programs binary data page by page
        * first writing the page data into the Tiberias write buffer
        * then performing a Tiberias program operation
        * progress(bytes_done), if given, is called after each page (it may
          raise an exception to abort between pages)
        """
        self.textToDisplay = ""  # used by GUI teminal
        prog_time = 0
        idx = 0
        addr = start_addr
        end_addr = start_addr + len(data_array)
        while addr < end_addr:
            pageEnd = addr - (addr % self.pageSize) + self.pageSize
            if pageEnd > end_addr:
                pageEnd = end_addr
            progSize = pageEnd - addr
            self.write_buf_write(comm, data_array[idx:idx+progSize], progSize)
            cmdstr = f'06;02 {addr:x} {progSize:x};wait 0'
            comm.send(cmdstr)
            addr = pageEnd
            self.textToDisplay += (cmdstr + '\t')

            page_prog_time_us = self.get_wait_time_us(comm)
            page_prog_time = self.time_conv_from_usec(page_prog_time_us)
            self.textToDisplay += f'(page program time: {page_prog_time})\n'

            prog_time += page_prog_time_us  # accumulating time for total time
            idx += progSize
            if progress:
                progress(idx)
        # calculating total program time and building the string for the terminal
        total_prog_time = self.time_conv_from_usec(prog_time)
        self.textToDisplay += f'Total Program time: {total_prog_time}\n'

        return self.get_wait_time_us(comm)


    def page_program(self, comm, start_addr=0, length=0, pattern='cafe0000',
                     increment='0', echo=0, progress=None, log_pages=True,
                     continuous=False):
        """Programs content of the write buffer into the memory\n
        Parameters:\n
        * start_addr (int): first memory location to program
        * length (int): number of bytes to program
        * pattern (8 digit hex string): 4-byte hex number to be programmed
        * increment (1-8 digit hex string) : +ve or -ve increment added to the pattern
        * echo (int): 0 or 1. Whether to print the results in the console or not
        * progress: progress(bytes_done, pages_done, address) is called after each page
          (it may raise an exception to abort between pages)
        * log_pages: False puts only a summary (pages, slowest page, total time) into
          textToDisplay, not one line per page (for large ranges)
        * continuous: False (default): the pattern is put in the write buffer once and every
          page gets the same words, so the counter restarts on each page. True: the pattern
          command is sent again before each page, with the value the counter has reached,
          so it keeps counting across pages (one more command per page)
        """
        self.textToDisplay = ""  # used by GUI terminal
        prog_time = 0
        pages, slowest, slowest_addr = 0, 0, start_addr
        # create a pattern in the write buffer
        cmdstr = f'pattern {pattern} {increment}'
        comm.send(cmdstr)
        if continuous:
            value = int(pattern, 16) & 0xFFFFFFFF
            step = int(increment, 16)       # may be negative
        addr = start_addr
        end_addr = start_addr + length
        while addr < end_addr:
            pageEnd = addr - (addr % self.pageSize) + self.pageSize
            if pageEnd > end_addr:
                pageEnd = end_addr
            progSize = pageEnd - addr
            if continuous and addr != start_addr:
                comm.send(f'pattern {value:08x} {increment}')
            cmdstr = f'06; 02 {addr:x} {progSize:x}; wait 0'
            if echo == 1:
                print(cmdstr)
            comm.send(cmdstr)
            pageStart, addr = addr, pageEnd
            if continuous:      # the counter after the words this page used
                value = (value + (progSize // 4) * step) & 0xFFFFFFFF

            page_prog_time_us = self.get_wait_time_us(comm)
            if log_pages:       # the page line for the GUI console
                page_prog_time = self.time_conv_from_usec(page_prog_time_us)
                self.textToDisplay += f'{cmdstr}\t(page program time: {page_prog_time})\n'

            prog_time += page_prog_time_us  # accumulating time for total time
            pages += 1
            if page_prog_time_us > slowest:
                slowest, slowest_addr = page_prog_time_us, pageStart
            if progress:
                progress(addr - start_addr, pages, pageStart)
        # calculating total program time and building the string for the terminal
        total_prog_time = self.time_conv_from_usec(prog_time)
        if not log_pages:
            self.textToDisplay += (f'{pages} pages, {length} bytes from {start_addr:x}; '
                                   f'slowest page {self.time_conv_from_usec(slowest)} '
                                   f'at {slowest_addr:x}\n')
        self.textToDisplay += f'Total Program time: {total_prog_time}\n'

        return self.get_wait_time_us(comm)

    def read_jedec_id(self, comm):
        """The JEDEC ID (command 9f 3) as a tuple of three ints, or None if the reply
        cannot be read"""
        self.read_id(comm, '9f ', 3, echo=0)
        reply = comm.response(removeCmd=True, removePrompt=True)
        found = [int(x, 16) for x in re.findall(r'\b[0-9a-fA-F]{2}\b', reply)]
        return tuple(found[:3]) if len(found) >= 3 else None

    @staticmethod
    def density_code(jedec):
        """Capacity code of a JEDEC ID: capacity in bytes = 2 ** code. None if unknown.
        Most devices give the code as the third byte (1f 42 18: 0x18 = 16 MB). Some
        Adesto / Atmel devices have a third byte that is not a code (1f 84 01, 1f 47 0c);
        their density is the low five bits of the second byte (4 = 4 Mbit, 7 = 32 Mbit)."""
        if not jedec:
            return None
        if 16 <= jedec[2] <= 40:                # 64 kB or more
            return jedec[2]
        if jedec[0] == 0x1F and 1 <= jedec[1] & 0x1F <= 20:
            return (jedec[1] & 0x1F) + 15       # 4 Mbit = 2 ** 19 bytes
        return None

    @staticmethod
    def chip_erase_estimate_s(jedec):
        """Expected chip erase time in seconds for a JEDEC ID: the measured time of a
        known device, else a guess from its capacity, else a default."""
        if jedec in MEASURED_ERASE_S:
            return MEASURED_ERASE_S[jedec]
        code = Dubrovnik.density_code(jedec)
        if code is None:
            return CHIP_ERASE_DEFAULT_S
        return ERASE_REF_S * (2 ** code / ERASE_REF_BYTES) ** ERASE_EXPONENT

    def chip_erase(self, comm, cancelRequested, trig=False):
        """Chip erase that can be cancelled: cancelRequested() is called about
        every 0.1 s while the board waits for the device. Returns the erase time in
        us, or None when it was cancelled (the device may be partly erased).
        self.eraseState is 'done', 'cancelled' or 'busy' (see BoardComm.send_cancellable)."""
        self.textToDisplay = ""
        if trig:
            cmdstr = f'{self.wel}; trig 1; c7; wait 0; trig 0\n'
        else:
            cmdstr = f'{self.wel}; c7; wait 0\n'
        self.eraseState = comm.send_cancellable(cmdstr, cancelRequested)
        if self.eraseState != 'done':
            return None
        erase_time = self.get_wait_time_us(comm)
        self.textToDisplay = f'Total Erase time: {self.time_conv_from_usec(erase_time)}\n'
        return erase_time

    def block_erase(self, comm, block_size=4, start_addr=0, num_blocks=1,
                    trig=False, echo=0, on_block=None):
        '''
        Parameters:
        comm       : handle of the communication port
        block_size : size of the memory block to be erased [kB]. Can be: 4kB, 32kB, 64kB or 'chip' for chip erase
        start_addr : start address (decimal) of the first erased block (aligned with the multiple of block_size)
        num_blocks : the number of blocks to erase (int)
        trig       : 'True' toggles a GPIO, HIGH at the beginning and LOW at the end of an Erase operation
                    (can be used to trigger a scope)
        on_block   : called with the text line of each block right after it was erased
                    (the Workbench prints it at once); textToDisplay then holds only the total
        echo       : '1' turns on printing intermediate commands sent to the flash,
                    also prints Erase Time

        Return value    : erase time in us/ms/sec (time it took to erase the specified chunk of memory block)
        '''
        self.textToDisplay = ""  # used by GUI
        erase_time = 0
        if block_size == 'chip':
            print('Chip Erase in progress...')
            opcode = 'c7'  # OpCode for chip erase: 60h or C7h
            if trig:
                cmdstr = f'{self.wel}; trig 1;{opcode}; wait 0; trig 0\n'
            else:
                cmdstr = f'{self.wel}; {opcode}; wait 0\n'
            comm.send(cmdstr)
            if echo == 1:
                print(comm.response(removePrompt=True))
            print('Done.')
            erase_time += self.get_wait_time_us(comm)
        else:
            blockSizeKB = block_size * 1024
            startAddr = (start_addr // blockSizeKB) * blockSizeKB
            if block_size == 4:
                opcode = '20'
            elif block_size == 32:
                opcode = '52'
            elif block_size == 64:
                opcode = 'd8'
            else:
                raise ValueError("Incorrect block size")
            addr = startAddr
            for _ in range(0, num_blocks):
                if trig:
                    cmdstr = f'{self.wel}; trig 1;{opcode} {addr:x}; wait 0; trig 0'
                else:
                    cmdstr = f'{self.wel}; {opcode} {addr:x}; wait 0'
                comm.send(cmdstr)
                if echo == 1:
                    print(comm.response(removePrompt=True))
                addr += blockSizeKB
                blk_ers_time_us = self.get_wait_time_us(comm)
                blk_ers_time = self.time_conv_from_usec(blk_ers_time_us)
                # the line for the terminal: at once, or collected in textToDisplay
                line = f'{cmdstr}\t(erase time: {blk_ers_time})'
                if on_block:
                    on_block(line)
                else:
                    self.textToDisplay += line + '\n'

                erase_time += blk_ers_time_us  # accumulating block erase time

                if echo == 1:
                    print(f'block erase time = {blk_ers_time}')
        # building total erase time and appending it to the terminal printout
        total_ers_time = self.time_conv_from_usec(erase_time)
        self.textToDisplay += f'Total Erase time: {total_ers_time}\n'

        # NOTE: chip boardcom may time out if chip erase time is too long (600sec or more)
        if echo == 1:
            print(f'Erase time = {erase_time} us')
        return erase_time

    def pmon_calib(self, comm, domain):
        self.pmoncfg(comm, avg=4, vbt=140, vst=2116, mode='sht', meas='i')
        cmdstr = f'pmon {domain} start; delay 100000; pmon {domain} stop; pmon {domain} calc'
        comm.send(cmdstr)
        resp = comm.response()
        print(resp)
        ibias = resp.split('\n')[1].split(' ')[-2]
        ibias_uA = int(1000 * float(ibias))
        ibias = str(ibias_uA)
        addr = int(domain) * 2
        cmdstr = f'write {addr:x} {ibias_uA}'
        comm.send(cmdstr)
        print(comm.response())
        comm.send('dispmode b')
        comm.send('dump w 0 10')
        print(comm.response())
        comm.send(f'eepwr {addr} 2')
        comm.send('eeprd 0 10')
        print(comm.response())

    def pmoncfg(self, comm, avg=None, vbt=None, vst=None, mode=None, meas=None):
        """### Configures the INA230 power monitor
        Parameters:
            avg  : number of averages
                [1 4 16 64 128 256 512 1024]
            vbt  : bus voltage conversion time [us]
                [140 204 332 588 1100 2116 4156 8244]
            vst  : shunt voltage conversion time [us]
                [140 204 332 588 1100 2116 4156 8244]
            meas : measurement subject
                i (current)
                v (voltage)
                iv (current and voltage)
                p (power)
            mode : svt (shunt voltage triggered)
                bvt (bus voltage triggered)
                sbt (shunt and bus triggered)
                svc (shunt voltage continuous)
                bvc (bus voltage continuous)
                sbc (shunt and bus continuous)
        """
        if avg is not None:
            cmdstr = f'pmoncfg avg {avg}'
            comm.send(cmdstr)
        if vbt is not None:
            cmdstr = f'pmoncfg vbt {vbt}'
            comm.send(cmdstr)
        if vst is not None:
            cmdstr = f'pmoncfg vst {vst}'
            comm.send(cmdstr)
        if mode is not None:
            cmdstr = f'pmoncfg mode {mode}'
            comm.send(cmdstr)
        if meas is not None:
            cmdstr = f'pmoncfg meas {meas}'
            comm.send(cmdstr)

    # Read opcode for each SPI mode shown in the GUI's Read panel
    READ_OPCODES = {'SPI': '0b',         # 1-1-1 fast read
                    'Dual': '3b',        # 1-1-2 dual output fast read
                    'Quad (114)': '6b',  # 1-1-4 quad output fast read
                    'Quad (144)': 'eb'}  # 1-4-4 quad I/O fast read
    # Opcodes with a mode byte between address and count: EB <addr> <mode> <count>
    # 00 = no continuous-read mode, so each read starts with a full opcode
    READ_MODE_BYTES = {'eb': '00'}
    QUAD_MODES = ('Quad (114)', 'Quad (144)')
    QE_MASK = 0x02                       # Quad Enable = bit 1 of status reg 2

    # The board's command table depends on the device. Opcode 35 is "Read Status Register 2" on
    # most devices, but "Read Sector Lockdown Registers 35 <address>" on others; there STS2 is
    # read with 05 2 (05 <count>: STS1 followed by STS2), and some devices take 05 without a
    # count. The board's own "help <opcode>" tells what a command is, so ask it (once per
    # connection) instead of keeping a list of devices. The wording is matched loosely:
    # "Status Register 2", "Status Register-2".
    STS2_HELP = re.compile(r'status\s*register[\s-]*2', re.IGNORECASE)

    def status_forms(self, comm):
        """How this device reads and writes the status registers, from the board's help:
        {'read2': '35' | '05 2' (STS1 then STS2), 'read1': '05' | '05 1', 'write2': '31' | '01'}.
        Asked once per connection (forget_status_forms() makes it ask again, e.g. when the
        device was changed). Anything the help does not make clear keeps the commands used
        so far (35, 05 and 31)."""
        if self.stsForms and self.stsForms[0] is comm:
            return self.stsForms[1]
        helps = {}
        for opcode in ('35', '5', '31', '1'):
            comm.send(f'help {opcode}')
            helps[opcode] = comm.response(removeCmd=True, removePrompt=True)
        counted = '<count>' in helps['5']
        forms = {
            'read1': '05 1' if counted else '05',
            'read2': ('35' if self.STS2_HELP.search(helps['35']) or not counted else '05 2'),
            'write2': ('31' if self.STS2_HELP.search(helps['31']) or helps['1'].count('<data>') < 2
                       else '01'),        # 01 <sts1> <sts2>
        }
        self.stsForms = (comm, forms)
        return forms

    def forget_status_forms(self):
        """The device (or the connection) changed: ask the board again next time"""
        self.stsForms = None

    def status_byte(self, comm, command):
        """Sends a status register read; the last byte of the reply is the register"""
        comm.send(command)
        reply = comm.response(removeCmd=True, removePrompt=True)
        try:
            return int(reply.split()[-1], 16)
        except (ValueError, IndexError):
            self.forget_status_forms()
            raise ValueError(f'Unexpected reply to "{command}" (status register): '
                             f'{reply.strip()!r}')

    def read_status2(self, comm):
        """Reads status register 2: 35, or 05 2 on the devices without 35 (see status_forms)"""
        return self.status_byte(comm, self.status_forms(comm)['read2'])

    def status2_write_command(self, comm, value):
        """The command that writes status register 2 (the caller sends it after the Write
        Enable): 31 <value>, or 01 <status register 1> <value> on the devices that write
        both registers together"""
        forms = self.status_forms(comm)
        if forms['write2'] == '01':
            return f'01 {self.status_byte(comm, forms["read1"]):02x} {value:02x}'
        return f'31 {value:02x}'

    def set_quad_enable(self, comm, enable):
        """Sets (enable=True) or clears the Quad Enable bit in status register 2.
        The write is skipped if the bit is already in the requested state
        (QE is non-volatile on most flash devices), and the result is verified
        by reading the register back. Raises ValueError if QE didn't change."""
        sr2 = self.read_status2(comm)
        new = (sr2 | self.QE_MASK) if enable else (sr2 & ~self.QE_MASK)
        if new != sr2:
            comm.send(f'{self.wel}; {self.status2_write_command(comm, new)}; wait 0')
            if self.read_status2(comm) != new:
                raise ValueError(
                    f'Quad Enable could not be {"set" if enable else "cleared"}'
                    f' (status register 2 is {sr2:02x}, expected {new:02x})')

    def read_mode(self, comm, spi_mode, start_addr=0, length=256, echo=1):
        """Reads flash using the read opcode of spi_mode (a key of READ_OPCODES).
        Quad Enable is set for the quad modes and cleared for SPI and Dual.
        Raises ValueError for a mode that is not supported."""
        if spi_mode not in self.READ_OPCODES:
            raise ValueError(f'SPI mode "{spi_mode}" is not supported yet')
        isQuad = spi_mode in self.QUAD_MODES
        opcode = self.READ_OPCODES[spi_mode]
        try:
            self.set_quad_enable(comm, isQuad)
        except IndexError:
            raise ValueError('Unexpected reply when reading status register 2')
        return self.read(comm, start_addr, length, echo,
                         opcode=opcode,
                         mode_byte=self.READ_MODE_BYTES.get(opcode))

    def pattern_program(self, comm, start_addr=0, end_addr=0,
                        pattern='cafe0000', increment=0, echo=0, continuous=False):
        """Programs the range [start_addr, end_addr) with a pattern (page by
        page). Same as page_program(), but takes an end address instead of a
        length, and accepts the increment as an integer or a hex string.
        Used by older scripts, e.g. get_vt_distribution_*.py.
        Returns the wait time (us) of the last page, like page_program()."""
        if isinstance(increment, int):
            increment = f'{increment:x}'
        return self.page_program(comm, start_addr, end_addr - start_addr,
                                 pattern, increment, echo, continuous=continuous)

    def echo(self, comm, onoff):
        """Turns the board's command echo 'on' or 'off' (the 'echo' command).
        Used by older scripts, e.g. debugging.get_vt_curves()."""
        if str(onoff).lower() not in ('on', 'off'):
            raise ValueError('echo must be "on" or "off"')
        comm.send(f'echo {str(onoff).lower()}')

    def set_spi_mode(self, spi_mode):
        """Returns the read opcode for a short mode name used by older scripts
        ('spi', 'q114', 'q144', 'q044'). The GUI uses read_mode() instead."""
        if spi_mode == 'spi':
            # READ OpCode in SPI: 03 (legacy), 0B (fast read)
            return '0b'
        elif spi_mode == 'q114':
            return '6b'                 # READ OpCode in QSPI 1-1-4
        elif spi_mode == 'q144':
            return 'eb'                 # READ OpCode in QSPI 1-4-4
        elif spi_mode == 'q044':
            return 'ebc'
        return None                     # 'qpi' and others: not supported yet

    def paint_flash_with_pattern(self, comm, params):
        """### Paint flash with pattern\n
        Parameters:\n
        comm: comm port to communicate with the Dubrovnik board
        params: a list of lists containing the [start address, length, pattern and increment]
        for each memory block to be programmed. It keeps programming until the list is exhausted\n
        [[start_address0, length0, pattern0, increment0]
        [start_address1, length1, pattern1, increment1]]
        .....
        [start_addressN, lengthN, patternN, incrementN]]
        Returns: the total programming time
        """
        prog_time = 0
        for param in params:
            start_addr = param[0]
            length = param[1]
            pattern = param[2]
            prog_time += self.page_program(comm,
                                           start_addr, length, pattern, echo=0)
        return prog_time


if __name__ == '__main__':
    comm = boardcom.BoardComm()
    comPort = comm.find_and_connect(echo=1)

    # Testing
    du = Dubrovnik()
    DBG = 0
    if DBG:
        cfg = du.get_config(comm)
        print(cfg)

    DBG = 0
    if DBG:
        print(du.get_part_number(comm))
        print('*****')
        du.get_version(comm, echo=1)
        print('*****')
        print(du.get_version(comm, echo=0))

    DBG = 0
    if DBG:
        comm.send('6; 20 20000; wait 0')
        print(comm.response())
        t_wait = du.get_wait_time_us(comm)
        print(f'Wait time: {du.time_conv_from_usec(t_wait)}')

    DBG = 1
    if DBG:
        du.set_dispmode(comm, 'w')
        comm.send('b 0 40')
        print(comm.response())

        resp = du.read(comm, start_addr=0, length=0x800, echo=1)
        print(resp)

    DBG = 0
    if DBG:
        erase_time = du.block_erase(comm, block_size=4, start_addr=0,
                                    num_blocks=1, echo=0)
        t_erase = du.time_conv_from_usec(erase_time)
        print(f'Erase time: {t_erase}')

    DBG = 1
    if DBG:
        t_wait = du.page_program(comm, start_addr=0, length=400, pattern='caba0000',
                                 increment=2, echo=1)
        t_prog = du.time_conv_from_usec(t_wait)
        print(f'Pattern program time: {t_prog}')
        # Verify if programming successful
        du.read(comm, echo=1)

    # ***** Disconnect
    comm.disconnect(comPort, echo=1)
