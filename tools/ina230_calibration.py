# TOOL: INA230 Calibration
# DESCRIPTION: calibrates the power monitor of the chosen power domains and stores the result in the board EEPROM
# CONFIRM: Calibrate the INA230 power monitors?\n\nThis erases the calibration stored in the board EEPROM and writes a new one. The sockets of the domains you calibrate must be empty.
#
# Ported from dub_calib.py to run inside the app. The instructions and the
# questions are dialogs now, and the script uses the app's connection. After
# the RESET you are asked for, it re-synchronises with the board instead of
# closing and reopening the COM port.

comm = dub.comm          # the board connection of the app


def extract_meas_in_ua(s):
    parts = s.split("=")
    fields = parts[1].split(" ")
    return float(fields[1]) * 1000.0


def int16_to_hex_le(x):
    s = format(x, '04x')
    return s[2:4] + s[0:2]


dub.message("Please follow these steps:\n\n"
            "1. Turn off the Dubrovnik power\n"
            "2. Empty the socket(s) associated with power domain(s)\n"
            "3. Make sure JP4 has pins 2-3 covered (VCC_ADJ connected)\n"
            "4. Turn on the Dubrovnik power\n"
            "5. Press the Dubrovnik RESET button\n\n"
            "Click OK when done.")
comm.connectToMCU()      # re-synchronise with the board after its reset
print("Board connected")

# Clear the EEPROM parameter data structure
comm.send("write 0 0000;eepwr 0 2")

dub.message("Please press the Dubrovnik RESET button one more time.\n\n"
            "Click OK when done.")
comm.connectToMCU()
print("Board connected")

num_meas = 5
bias_list = []
eep_str = "50410200"
n_domains = 0

while True:
    n_domains += 1
    bias_entry = [0, 0, 0]
    while True:
        answer = dub.ask("Enter the next power domain to be calibrated "
                         "(0-32, example: 5 - SOIC socket):")
        if answer is None:
            raise SystemExit           # cancelled
        try:
            domain = int(answer)
        except ValueError:
            continue
        if 0 <= domain <= 32:
            break
    bias_entry[0] = domain

    print("calibrating domain %d..." % domain)
    for column, volts in ((1, "1.6"), (2, "3.6")):
        meas_avg = 0.0
        for _ in range(num_meas):
            comm.send("volt %s;delay 200000" % volts)
            comm.send("pmon %d start;delay 100000;pmon %d stop;pmon %d calc"
                      % (domain, domain, domain))
            meas_avg += extract_meas_in_ua(comm.response())
            dub.sleep(0)               # keep the window alive, check for Esc
        bias_entry[column] = round(meas_avg / num_meas)

    bias_list.append(bias_entry)
    print("domain %d: %d uA at 1.6 V, %d uA at 3.6 V"
          % (domain, bias_entry[1], bias_entry[2]))

    if not dub.confirm("Calibrate another domain?"):
        break

print("calibration done, writing to EEPROM...")

eep_str += int16_to_hex_le(n_domains * 6)
for entry in bias_list:
    eep_str += int16_to_hex_le(entry[0])
    eep_str += int16_to_hex_le(entry[1])
    eep_str += int16_to_hex_le(entry[2])

remaining = len(eep_str)
i = 0
while remaining > 0:
    wsize = 32 if remaining > 32 else remaining
    comm.send("write 0 " + eep_str[i: i + wsize])
    comm.send("eepwr " + format(i // 2, 'x') + " " + format(wsize // 2, 'x'))
    i += wsize
    remaining -= wsize

comm.send("write 0 ffff")
comm.send("eepwr " + format(i // 2, 'x') + " 2")

print("Done")
