"""Settings: defaults, loading with bad values, saving, the params, the old file."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dubLibs.settings import DEFAULTS, PARAM_KEYS, Settings  # noqa: E402


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='dub_settings_')
        self.folder = os.path.join(self.root, 'Dubrovnik')     # created by Settings
        self.addCleanup(shutil.rmtree, self.root, True)

    def write(self, data, name='dubrovnik_workbench.cfg'):
        os.makedirs(self.folder, exist_ok=True)
        with open(os.path.join(self.folder, name), 'w', encoding='utf-8') as fh:
            fh.write(data if isinstance(data, str) else json.dumps(data))

    def read(self):
        with open(os.path.join(self.folder, 'dubrovnik_workbench.cfg'), encoding='utf-8') as fh:
            return json.load(fh)

    def test_hex_options_are_the_keywords_of_hexdump(self):
        s = Settings(self.folder)
        s.hexRow, s.hexAscii, s.hexUpper, s.hexGap = 8, False, True, False
        self.assertEqual(s.hexOptions(), dict(per_row=8, show_ascii=False, upper=True, gap=False))

    def test_creates_the_folder_and_starts_with_the_defaults(self):
        s = Settings(self.folder)
        self.assertTrue(os.path.isdir(self.folder))
        self.assertEqual((s.appearance, s.termTheme, s.termFont, s.termFontSize),
                         ('system', 'dark', 'Consolas', 15))
        self.assertEqual((s.hexRow, s.hexAscii, s.hexUpper, s.hexGap), (16, True, True, True))
        self.assertEqual((s.showPanels, s.winSize, s.winPos), (True, None, None))

    def test_no_file_gives_defaults_status_and_resets_the_connection_settings(self):
        s = Settings(self.folder)
        s.autoConnect, s.lastUsedPort = 1, 'COM9'
        self.assertEqual(s.load(), ('defaults', None))
        self.assertEqual((s.autoConnect, s.lastUsedPort), (0, ''))

    def test_damaged_file_is_kept_as_bad_and_gives_defaults(self):
        self.write('{ not json')
        s = Settings(self.folder)
        self.assertEqual(s.load()[0], 'defaults')
        self.assertTrue(os.path.isfile(s.cfgFile + '.bad'))

    def test_roundtrip_of_the_settings(self):
        s = Settings(self.folder)
        s.autoConnect, s.lastUsedPort = 1, 'COM7'
        s.appearance, s.termTheme, s.termFontSize = 'dark', 'light', 18
        s.hexRow, s.hexAscii, s.showPanels = 32, False, False
        s.datasheetUrl = 'https://example.com/{part}'
        s.winSize, s.winPos = (900, 700), (10, 20)
        self.assertTrue(s.save())
        t = Settings(self.folder)
        status, params = t.load()
        self.assertEqual(status, 'ok')
        self.assertEqual((t.autoConnect, t.lastUsedPort, t.appearance, t.termTheme, t.termFontSize),
                         (1, 'COM7', 'dark', 'light', 18))
        self.assertEqual((t.hexRow, t.hexAscii, t.showPanels), (32, False, False))
        self.assertEqual((t.datasheetUrl, t.winSize, t.winPos),
                         ('https://example.com/{part}', (900, 700), (10, 20)))
        self.assertEqual(params, {k: DEFAULTS[k] for k in PARAM_KEYS})

    def test_script_options_default_on_roundtrip_and_bad_values(self):
        s = Settings(self.folder)
        self.assertEqual((s.scriptListing, s.scriptComments), (True, True))
        s.scriptListing, s.scriptComments = False, False
        s.save()
        t = Settings(self.folder)
        t.load()
        self.assertEqual((t.scriptListing, t.scriptComments), (False, False))
        self.write({'showScriptListing': 'maybe', 'showScriptComments': 5})
        u = Settings(self.folder)
        u.load()
        self.assertEqual((u.scriptListing, u.scriptComments), (True, True))

    def test_bad_values_fall_back_to_their_defaults(self):
        self.write({'appearance': 'purple', 'terminalTheme': 'neon', 'terminalFontSize': 'big',
                    'hexBytesPerRow': 12, 'terminalBg': 'red',
                    'windowWidth': 5, 'windowHeight': 5})
        s = Settings(self.folder)
        self.assertEqual(s.load()[0], 'ok')
        self.assertEqual((s.appearance, s.termTheme, s.termFontSize, s.hexRow),
                         ('system', 'dark', 15, 16))
        self.assertEqual(s.termBg, DEFAULTS['terminalBg'])
        self.assertIsNone(s.winSize)               # outside 200..20000

    def test_choices_of_the_caller_are_checked(self):
        self.write({'readSpiMode': 'XYZ', 'eraseBlkSize': '64'})
        _, params = Settings(self.folder).load(choices={'readSpiMode': ('SPI', 'QPI'),
                                                        'eraseBlkSize': ('4', '32', '64')})
        self.assertEqual((params['readSpiMode'], params['eraseBlkSize']), ('SPI', '64'))

    def test_params_are_saved_only_when_given_and_kept_otherwise(self):
        s = Settings(self.folder)
        stored = {k: 'A' for k in PARAM_KEYS}
        s.save(params=stored)
        s.termFontSize = 20
        s.save()                                       # no params: the stored ones stay
        data = self.read()
        self.assertEqual(data['progPattern'], 'A')
        self.assertEqual(data['terminalFontSize'], 20)

    def test_unknown_keys_in_the_file_survive_a_save(self):
        self.write({'somethingNew': 42})
        s = Settings(self.folder)
        s.load()
        s.save()
        self.assertEqual(self.read()['somethingNew'], 42)

    def test_load_without_prefs_leaves_the_attributes_alone(self):
        self.write({'terminalFontSize': 22, 'progPattern': 'beef'})
        s = Settings(self.folder)
        status, params = s.load(prefs=False)
        self.assertEqual((status, s.termFontSize, params['progPattern']), ('ok', 15, 'beef'))

    def test_start_folders_that_do_not_exist_are_dropped(self):
        self.write({'commandScriptFolder': os.path.join(self.root, 'nope'),
                    'pythonScriptFolder': self.root, 'programFolder': self.root,
                    'userToolsFolder': os.path.join(self.root, 'away')})
        s = Settings(self.folder)
        s.load()
        self.assertEqual((s.commandDir, s.pythonDir, s.programDir), ('', self.root, self.root))
        self.assertEqual(s.userToolsDir, os.path.join(self.root, 'away'))     # kept as typed

    def test_first_run_takes_over_the_old_classic_file_without_its_window_entries(self):
        self.write({'terminalFontSize': 19, 'mainWindowWidth': 800, 'windowWidth': 777},
                   name='dubrovnik.cfg')
        s = Settings(self.folder)
        self.assertTrue(os.path.isfile(s.cfgFile))
        data = self.read()
        self.assertEqual(data['terminalFontSize'], 19)
        self.assertNotIn('mainWindowWidth', data)
        s.load()
        self.assertEqual(s.termFontSize, 19)

    def test_an_existing_new_file_is_not_replaced_by_the_old_one(self):
        self.write({'terminalFontSize': 11})
        self.write({'terminalFontSize': 19}, name='dubrovnik.cfg')
        Settings(self.folder)
        self.assertEqual(self.read()['terminalFontSize'], 11)


if __name__ == '__main__':
    unittest.main()
