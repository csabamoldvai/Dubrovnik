# TOOL: Icc Read Measurement
# DESCRIPTION: reads the flash in several modes and measures the supply current (result file in Documents\Dubrovnik\Results)
# CONFIRM: Measure the read current of the device in the socket?\n\nThe voltage and the SPI clock are changed while it runs, and the Quad Enable bit is set and cleared. If you choose to paint the memory, 4 blocks at each pattern address are erased and reprogrammed.
#
# Ported from icc_read_meas.py to run inside the app. It uses the app's
# connection (dub.comm), asks for the device number, temperature and whether to
# paint the memory in dialogs, and saves its result file in
# Documents\Dubrovnik\Results. Edit the settings below to change the test.

import time

comm = dub.comm          # the board connection of the app
du = dub.du              # the Dubrovnik library object

# ***** Test settings (edit here) *****
pmon_id = '5'
spi_mode = ['spi', 'q144']       # choose from: 'spi', 'q114', 'q144', 'q044'
set_voltage = [1.8]              # [V]; must stay within the device's limits
set_freq = [64]                  # [MHz]
# *************************************

deviceNum = dub.ask('Device number:', '01')
if deviceNum is None:
    raise SystemExit
temperature = dub.ask('Temperature label for the result file (e.g. 25C):', '25C')
if temperature is None:
    raise SystemExit
PAINT_MEMORY = dub.confirm('Paint the memory with the test patterns first?\n\n'
                           'Choose No if the device already holds them.')

du.set_dispmode(comm, 'w')
config = du.get_config(comm)
partNumber = config['Part#']
voltage = config['Voltage']
freq = config['Frequency']

print(f"Device Number : {deviceNum}")
print(f"Part Number   : {partNumber}")
print(f"Voltage       : {voltage}V")
print(f"Frequency     : {freq}MHz")

print('Status Registers:')
du.read_id(comm, narg=2)

# PAINT MEMORY BIT PATTERN
# 0x0000-0x3fff   : "aaaaaaaa"
# 0x4000-0x7fff   : "00000000"
# 0x8000-0xbfff   : "ffffffff"
# 0xc000-0xffff   : "f0f0f0f0"
# 0x10000-0x13fff : "ff00ff00"
paint_flash_params = [[0x0000, 0x4000, 'aaaaaaaa'],
                      [0x4000, 0x4000, '00000000'],
                      [0x8000, 0x4000, 'ffffffff'],
                      [0xc000, 0x4000, 'f0f0f0f0'],
                      [0x10000, 0x4000, 'ff00ff00']]

if PAINT_MEMORY:
    print('\nErasing memory blocks...')
    for item in paint_flash_params:
        du.block_erase(comm, start_addr=item[0], block_size=4, num_blocks=4, echo=1)
    print('Wait!!! Painting memory...')
    prog_time = du.paint_flash_with_pattern(comm, paint_flash_params)
    print(f'Programming time: {du.time_conv_from_usec(prog_time)}')

for param in paint_flash_params:
    du.read(comm, param[0], 0x20, echo=1)

# To make sure the device is not damaged, check the selected voltages first
for v in set_voltage:
    v_max = float(voltage) + 0.3
    if v > v_max:
        print('\nCAUTION!!!\n')
        print(f'Specified voltage: {v:.3f}V exceeds device Abs Max Limits: {v_max:.3f}V\n')
        raise SystemExit

# *************************************************
# *****     READ DEVICE - MEASURE CURRENT     *****
# *************************************************
print('Read device')

fname = dub.output_path(f'{partNumber} UNIT {deviceNum} {temperature}.txt')
file = open(fname, 'w')
try:
    file.write(f'Part Number: {partNumber}\n')
    file.write(f'Temperature: {temperature}\n')
    file.write(f'Unit: {deviceNum}\n')
    file.write(' Mode  Vcc[V] freq[MHz] Icc1[mA] t_elapsed[us] num_errors start_address\n')
    file.write(' ----------------------------------------------------------------------\n')

    tot_error_cnt = 0
    err_cnt = 0

    for mode in spi_mode:
        # ATTENTION: IMPORTANT! Set the Quad Enable bit. This command may be
        # different for different devices.
        if mode[0].lower() == 'q':
            comm.send('6; 31 2')
            comm.send('35')
            start_addr = paint_flash_params[3][0]
            wr_buff = paint_flash_params[3][2]
        else:
            comm.send('6; 31 0')
            comm.send('35')
            start_addr = paint_flash_params[0][0]
            wr_buff = paint_flash_params[0][2]

        print(f'Start Address: 0x{start_addr:x}\n')
        addr = start_addr

        print('Read Status Registers - checking QE bit:')
        comm.send('05; 35')
        print(comm.response())

        read_opcode = du.set_spi_mode(mode)
        print(f'MODE: {mode}')

        for v in set_voltage:
            comm.send(f'psset 0 {v}')           # set voltage

            for f in set_freq:
                comm.send(f'freq {f}')          # set frequency
                read_str = ''

                N = 16
                read_block_size = 0x4000
                block = f'{read_block_size:x}'

                for n in range(0, N):
                    if mode == 'q144':
                        addon = f'{read_opcode} {addr:x} 00 {block};'
                    elif mode == 'q044':
                        if n == 0:
                            addon = f'eb {addr:x} a0 {block};'
                        elif n == N - 1:
                            addon = f'ebc {addr:x} 00 {block};'
                        else:
                            addon = f'ebc {addr:x} a0 {block};'
                    else:
                        addon = f'{read_opcode} {addr:x} {block};'
                    read_str += addon

                # All power monitoring commands are inline with the reads to
                # exclude delays introduced by the Python interpreter
                read_str = (f'pmon {pmon_id} start;timer start;{read_str} '
                            f'timer stop; pmon {pmon_id} stop')
                print(read_str)

                comm.send('echo off')
                start_time = time.time()
                comm.send(read_str)
                end_time = time.time()
                comm.send('echo on')
                comm.send('dvar elapsed_time')
                e_time = comm.response().split('\n')
                print(e_time[1])
                comm.send(f'pmon {pmon_id} calc')
                pmon1 = comm.response()
                print(pmon1)

                print(f'Total elapsed time: {round(end_time - start_time, 3)}\n')

                # ***** SAVE RESULTS *****
                ch1 = pmon1.index('=')      # position of '='
                ch2 = pmon1.index('mA')
                # between these is the current; drop the 'mA'
                icc1 = pmon1[ch1 + 1: ch2 - 1]

                # Verify that the data read matches the reference pattern
                comm.send(f'pattern {wr_buff} 0')      # reference into the write buffer
                comm.send(f'cmp 0 {read_block_size:x}')
                comp_result_msg = comm.response()

                # if the reply doesn't contain 'equal', the buffers differ
                if 'equal' not in comp_result_msg.lower():
                    err_msg = comp_result_msg.split('\n')[-1]
                    print(err_msg)
                    try:
                        err_cnt = int(err_msg.split()[-2])
                    except (IndexError, ValueError):
                        print('Buffer overload!!! Printout of differences not available.\n'
                              'Use the cmp command in the Terminal to explore it.')
                        err_cnt = -1
                    tot_error_cnt += 1

                file.write(f'{mode:>5s} {v:>6.2f}     {f:>5.2f}  {icc1:>7s}   '
                           f'{e_time[1][:-2]:>12s}     {err_cnt:>6d}    {start_addr:>10x}\n')
                err_cnt = 0

    file.write(f'\nNumber of failed cases {tot_error_cnt}\n')
finally:
    file.close()

print(f'\nResults saved in: {fname}')
