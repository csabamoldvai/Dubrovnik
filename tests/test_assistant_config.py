"""assistant_config (saved credentials) and assistant.resolve / configured."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dubLibs import assistant, assistant_config  # noqa: E402

ENV_NAMES = ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL',
             'DUB_ASSISTANT_PROVIDER', 'DUB_ASSISTANT_MODEL', 'ANTHROPIC_VERTEX_PROJECT_ID',
             'CLOUD_ML_REGION')


class CleanEnvironment(unittest.TestCase):
    def setUp(self):
        env = {k: v for k, v in os.environ.items() if k not in ENV_NAMES}
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)


class SavedFileTests(CleanEnvironment):
    def setUp(self):
        super().setUp()
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def test_round_trip_and_the_key_is_not_written_in_clear(self):
        cfg = {'provider': 'anthropic', 'apiKey': 'sk-secret-123', 'model': 'm1'}
        self.assertTrue(assistant_config.save(self.dir.name, cfg))
        with open(os.path.join(self.dir.name, 'assistant.cfg'), encoding='utf-8') as fh:
            text = fh.read()
        self.assertNotIn('sk-secret-123', text)
        loaded = assistant_config.load(self.dir.name)
        self.assertEqual((loaded['provider'], loaded['apiKey'], loaded['model']),
                         ('anthropic', 'sk-secret-123', 'm1'))
        self.assertEqual(loaded['baseUrl'], '')

    def test_missing_or_damaged_file_gives_empty_settings(self):
        self.assertEqual(assistant_config.load(self.dir.name)['provider'], '')
        with open(os.path.join(self.dir.name, 'assistant.cfg'), 'w') as fh:
            json.dump({'provider': 'bogus', 'apiKey': 'dpapi:!!not base64', 'model': 5}, fh)
        loaded = assistant_config.load(self.dir.name)
        self.assertEqual((loaded['provider'], loaded['apiKey'], loaded['model']), ('', '', ''))

    def test_empty_key_stays_empty(self):
        self.assertEqual(assistant_config.protect(''), '')
        self.assertEqual(assistant_config.unprotect(''), '')


class ResolveTests(CleanEnvironment):
    def test_nothing_set(self):
        self.assertFalse(assistant.configured())
        self.assertFalse(assistant.configured({'provider': 'anthropic', 'apiKey': ''}))

    def test_saved_settings_make_it_configured(self):
        self.assertTrue(assistant.configured({'provider': 'anthropic', 'apiKey': 'k'}))
        self.assertFalse(assistant.configured({'provider': 'gateway', 'apiKey': 'k'}))
        self.assertTrue(assistant.configured(
            {'provider': 'gateway', 'apiKey': 'k', 'baseUrl': 'https://gw'}))
        self.assertTrue(assistant.configured({'provider': 'bedrock'}))

    def test_environment_fills_what_is_empty(self):
        os.environ['ANTHROPIC_API_KEY'] = 'envkey'
        os.environ['DUB_ASSISTANT_MODEL'] = 'envmodel'
        c = assistant.resolve({'provider': 'anthropic', 'apiKey': '', 'model': ''})
        self.assertEqual((c['apiKey'], c['model']), ('envkey', 'envmodel'))
        c = assistant.resolve({'provider': 'anthropic', 'apiKey': 'saved', 'model': 'mine'})
        self.assertEqual((c['apiKey'], c['model']), ('saved', 'mine'))

    def test_environment_alone_still_works(self):
        os.environ['ANTHROPIC_AUTH_TOKEN'] = 't'
        os.environ['ANTHROPIC_BASE_URL'] = 'https://gw'
        c = assistant.resolve(None)
        self.assertEqual((c['provider'], c['apiKey'], c['baseUrl']), ('gateway', 't', 'https://gw'))
        self.assertTrue(assistant.configured())

    def test_default_model_and_region(self):
        c = assistant.resolve({'provider': 'vertex'})
        self.assertEqual((c['model'], c['vertexRegion']), (assistant.DEFAULT_MODEL, 'global'))


if __name__ == '__main__':
    unittest.main()
