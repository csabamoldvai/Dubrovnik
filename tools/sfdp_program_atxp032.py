# TOOL: SFDP Program (ATXP032)
# DESCRIPTION: rewrites the SFDP table of the ATXP032 in the socket and compares it afterwards
# CONFIRM: Rewrite the SFDP table of the device in the socket?\n\nThis is meant for an ATXP032 only. The SFDP area is erased and reprogrammed.
#
# Ported from atxp032_sfdp_reprogram_autodetect.py to run inside the app: it
# uses the app's connection through the `dub` object.

print('Dump SFDP before patch')
print(dub.send('5a 0 100', echo=False))

dub.send('c0', echo=False)
dub.send('C2 01', echo=False)
dub.send('F4 08', echo=False)
dub.send('F6 80', echo=False)
dub.send('C2 02', echo=False)
dub.send('F8 00', echo=False)

dub.send('06; 81 800; wait 0', echo=False)

# ATXP032 SFDP table, 16 bytes per line
SFDP = [
    'write 00 53464450070103FC00070114280000FF',
    'write 10 05000105780000FF8700011C8C0000FF',
    'write 20 0A000104D40000FFFD208CFFFFFFFF01',
    'write 30 0000000000000000EEFFFFFFFFFF0000',
    'write 40 FFFF00000C200F5210D800FF904A4E01',
    'write 50 80BF94E220610644D0B0D0B0F7A7D55C',
    'write 60 000000FF82000040000000000000FC01',
    'write 70 21001000000042620C0B008071716565',
    'write 80 00E494DC000000000C57240000000000',
    'write 90 8000000008D1FFC708D1FFC70005C480',
    'write a0 0005C4810005C4A50005C4A5716503D0',
    'write b0 000000009C0000008823599A00000086',
    'write c0 00000000000000007165029300000000',
    'write d0 71650297000006010000000088027104',
    'write e0 0000000600000000716501D6716501D4',
    'write f0 00000000716501D000003805FFFFFFFF',
]
for line in SFDP:
    dub.send(line, echo=False)

dub.send('06; 02 800 100; wait 0', echo=False)

dub.send('c1', echo=False)
dub.send('c3 d0', echo=False)

dub.send('jrst', echo=False)
dub.sleep(0.1)

print('Dump SFDP after patch')
print(dub.send('5a 0 100', echo=False))

print(dub.send('cmp 0 100', echo=False))
