# TOOL: My Test
# DESCRIPTION: DAC/ADC, power monitors, LEDs, device program/erase/read and V_ADJ checks
# CONFIRM: Run the Dubrovnik functional test?\n\nIt erases and programs block 0 of the device in the socket (if one is installed), and changes the supply voltage while it runs.
#
# Ported from dubrovnik_func_verify.py to run inside the app: it uses the app's
# connection through the `dub` object instead of opening its own COM port.
# Everything it prints appears in the Terminal; the summary is at the end.

results = []          # (test name, passed)


def check(name, passed):
    results.append((name, passed))
    return 'PASS' if passed else 'FAIL'


def lines_of(reply):
    return reply.splitlines()


print('********************************')
print('***** DUBROVNIK TEST START *****')
print('********************************\n')

# ENTER System Parameters Here
freq = 8   # choose 8 (8.25), 15 (14.67) or 30 (29.33)  [MHz]

dub.send('freq %d' % freq, echo=False)
dub.send('dispmode w', echo=False)

# Read board configuration
print(dub.send('ver', echo=False))
config = dub.du.get_config(dub.comm)
print(config)
partNumber = config['Part#'].upper()
voltage = config['Voltage']
min_dly = int(config['min meas time (us)'])

if partNumber == 'UNKNOWN':
    voltage = '1.8'   # don't go higher, it may damage the MCU VCC_SD input

# the previous run may have left the supply at a low voltage
dub.send('psset 0 %s' % voltage, echo=False)

# ---------------------------------------------------------------------------
print('\n ********** DAC, ADC TEST **********')
dub.send('muxset 1', echo=False)    # select the DAC and route it to the MUX output
for dacval in ('7ff', '400', '200', '100'):
    dub.send('dacset %s' % dacval, echo=False)
    dub.send('adcstart c8', echo=False)          # configure ADC, start conversion
    reply = dub.send('adcread', echo=False)       # read result of A/D conversion
    Dadc = lines_of(reply)[0].split()[2]
    adc = int(Dadc, 0)
    dac = int(dacval, 16)
    ok = .975 * dac < adc < 1.025 * dac
    msg = '\tDAC=0x%s => ADC=%s ' % (dacval, Dadc)
    print(msg + ('' if ok else '(incorrect ADC value) ') + check('DAC/ADC 0x' + dacval, ok))
dub.send('muxset 0', echo=False)    # restore MUX: CS# goes to the flash

# ---------------------------------------------------------------------------
print('\n ********** PMON TEST **********')
dub.send('pmoncfg meas iv', echo=False)
for pmon_id in range(5):
    reply = dub.send('pmon %d start; timer start; delay %s; timer stop; '
                     'pmon %d stop; pmon %d calc'
                     % (pmon_id, 1.2 * min_dly, pmon_id, pmon_id),
                     echo=False, check=False)
    if 'i2c error' in reply:
        print('\tPMON %d: i2c error  %s' % (pmon_id, check('PMON %d' % pmon_id, False)))
        continue
    try:
        i_v = lines_of(reply)[0].split(' ')
        curr, volt = i_v[2], i_v[6]
        print('\tPMON %d: %5s V, %5s mA  %s'
              % (pmon_id, volt, curr, check('PMON %d' % pmon_id, True)))
    except IndexError:
        print('\tPMON %d: unexpected reply: %s  %s'
              % (pmon_id, reply.strip(), check('PMON %d' % pmon_id, False)))

# ---------------------------------------------------------------------------
print('\n ********** LED TEST (visual check) **********')
led = [{'gpio': '9', 'color': 'RGB LED: RED'},
       {'gpio': '10', 'color': 'RGB LED: BLUE'},
       {'gpio': '11', 'color': 'RGB LED: GREEN'},
       {'gpio': '12', 'color': 'LED: BLUE'},
       {'gpio': '13', 'color': 'LED: GREEN'},
       {'gpio': '14', 'color': 'LED: RED'}]


def set_leds(on):
    for item in led:
        dub.send('gpiocfg %s o' % item['gpio'], echo=False)
        dub.send('gpiowr %s %d' % (item['gpio'], 0 if on else 1), echo=False)
        print('\t%s %s' % (item['color'], 'ON' if on else 'OFF'))
        dub.sleep(.3)


print('Turn LEDs off')
set_leds(False)
print('Turn LEDs on')
set_leds(True)

# ---------------------------------------------------------------------------
print('\n ********** Device Program/Erase/Read Test **********')
if partNumber[0:2] == 'AT':          # device present
    print('Device %s present' % partNumber)
    print('VCC = %sV' % voltage)
    print('Read Status Registers:')
    if partNumber[2:4] == 'XP':       # global unprotect for EcoXiP
        dub.send('39 0', echo=False)
        dub.send('6; 71 1 0', echo=False)           # STSREG2[3:2]="00"
        reply = dub.send('65 1; 65 2', echo=False)  # status register read
    else:
        reply = dub.send('05; 35', echo=False)
    sts = lines_of(reply)
    print('STSREG1: %s' % sts[0])
    print('STSREG2: %s' % sts[1])

    print('\n    Erasing block 0...')
    dub.send('6;20 0; wait 0', echo=False)
    print('    Reading...')
    data = lines_of(dub.send('b 0 20', echo=False))[0]
    print('\t%s' % data)
    if 'ffffffff' in data:
        print('DEVICE ERASED')

    print('\n    Programming...')
    dub.send('pattern caba0000 1', echo=False)
    dub.send('06; 02 0 20; wait 0', echo=False)
    print('    Reading...')
    data = lines_of(dub.send('0b 0 20', echo=False))[0]
    print('\t%s' % data)
    ok = 'caba0000' in data
    print('\nPROGRAM/READ ' + check('Program/Read', ok))

    print('\n    Erasing block 0...')
    dub.send('6;20 0; wait 0', echo=False)
    data = lines_of(dub.send('0b 0 20', echo=False))[0]
    print('\t%s' % data)
    print('\nERASE ' + check('Erase', 'ffffffff' in data))
else:
    print('No Atmel/Adesto "AT" device recognised in the socket: test skipped.')

# ---------------------------------------------------------------------------
print('\n ********** V_ADJ TEST **********')
dub.send('pmoncfg meas v', echo=False)
vmin = 0.9                 # minimum voltage of the LDO
vmax = float(voltage)
step = 10
K = (vmax - vmin) / step
epsilon = .04              # max allowed voltage difference [V]

dub.send('psset 0 0', echo=False)   # turn off the power supply
dub.sleep(1)                        # wait for the capacitors to discharge

print('\tVset[V] Vmeas[V] Diff')
for i in range(step):
    v = vmax - K * i
    dub.send('psset 0 %.3f' % v, echo=False)
    dub.sleep(.5)                   # voltage needs time to settle
    reply = dub.send('pmon 1 start; delay 100000; pmon 1 stop; pmon 1 calc',
                     echo=False, check=False)
    try:
        vmeas = float(lines_of(reply)[0].split(' ')[2])
    except (IndexError, ValueError):
        print('\t %.3f   unexpected reply: %s  %s'
              % (v, reply.strip(), check('V_ADJ %.3f V' % v, False)))
        continue
    ok = (v - epsilon) < vmeas < (v + epsilon)
    print('\t %.3f   %.3f %3.0fmV  : %s'
          % (v, vmeas, (v - vmeas) * 1000, check('V_ADJ %.3f V' % v, ok)))

dub.send('psset 0 %s' % vmax, echo=False)   # restore the starting value

print('\nTurn LEDs off')
set_leds(False)

# ---------------------------------------------------------------------------
failed = [name for name, passed in results if not passed]
print('\n*******************************')
print('******** TEST FINISHED ********')
print('*******************************')
print('%d checks, %d passed, %d failed' % (len(results), len(results) - len(failed), len(failed)))
if failed:
    print('FAILED: ' + ', '.join(failed))
print('RESULT: ' + ('FAIL' if failed else 'PASS'))
