import os
import unittest
from unittest import mock

from slacker.api import slack_headers
from slacker.auth import (
    _parse_export_value,
    credentials_from_env,
    read_auth_file,
    resolve_credentials,
)


class ParseExportValueTests(unittest.TestCase):
    def test_strips_quotes(self):
        self.assertEqual(_parse_export_value('"abc"'), 'abc')

    def test_expands_env(self):
        with mock.patch.dict(os.environ, {'SLACK_BOT_TOKEN': 'xoxb-from-env'}):
            self.assertEqual(_parse_export_value('"$SLACK_BOT_TOKEN"'), 'xoxb-from-env')

    def test_unset_env_is_empty(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_parse_export_value('"$SLACK_BOT_TOKEN"'), '')


class CredentialsFromEnvTests(unittest.TestCase):
    def test_bot_token_without_cookie(self):
        env = {'SLACK_BOT_TOKEN': 'xoxb-bot'}
        with mock.patch.dict(os.environ, env, clear=True):
            creds = credentials_from_env()
        self.assertEqual(creds['token'], 'xoxb-bot')
        self.assertIsNone(creds['cookie'])
        self.assertEqual(creds['source'], 'SLACK_BOT_TOKEN')

    def test_session_token_requires_cookie(self):
        with mock.patch.dict(os.environ, {'SLACK_TOKEN': 'xoxc-user'}, clear=True):
            self.assertIsNone(credentials_from_env())

    def test_session_token_with_cookie(self):
        env = {'SLACK_TOKEN': 'xoxc-user', 'SLACK_COOKIE': 'xoxd-cookie'}
        with mock.patch.dict(os.environ, env, clear=True):
            creds = credentials_from_env()
        self.assertEqual(creds['cookie'], 'xoxd-cookie')

    def test_bot_token_wins_over_session(self):
        env = {
            'SLACK_BOT_TOKEN': 'xoxb-bot',
            'SLACK_TOKEN': 'xoxc-user',
            'SLACK_COOKIE': 'xoxd-cookie',
        }
        with mock.patch.dict(os.environ, env, clear=True):
            creds = credentials_from_env()
        self.assertEqual(creds['token'], 'xoxb-bot')


class ReadAuthFileTests(unittest.TestCase):
    def test_bot_token_line_without_cookie(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'credentials'
            path.write_text('export SLACK_BOT_TOKEN="xoxb-file"\n')
            with mock.patch.dict(os.environ, {}, clear=True):
                creds = read_auth_file(str(path))
            self.assertEqual(creds['token'], 'xoxb-file')
            self.assertIsNone(creds['cookie'])

    def test_file_expands_bot_token_env(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'credentials'
            path.write_text('export SLACK_BOT_TOKEN="$SLACK_BOT_TOKEN"\n')
            with mock.patch.dict(os.environ, {'SLACK_BOT_TOKEN': 'xoxb-expanded'}):
                creds = read_auth_file(str(path))
            self.assertEqual(creds['token'], 'xoxb-expanded')


class ResolveCredentialsTests(unittest.TestCase):
    def test_prefer_env_skips_file(self):
        with mock.patch.dict(os.environ, {'SLACK_BOT_TOKEN': 'xoxb-env'}, clear=True):
            creds = resolve_credentials('/no/such/file', prefer_env=True)
        self.assertEqual(creds['source'], 'SLACK_BOT_TOKEN')

    def test_explicit_file_ignores_env(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'credentials'
            path.write_text(
                'export SLACK_TOKEN="xoxc-file"\nexport SLACK_COOKIE="xoxd-file"\n'
            )
            env = {'SLACK_BOT_TOKEN': 'xoxb-env'}
            with mock.patch.dict(os.environ, env, clear=True):
                creds = resolve_credentials(str(path), prefer_env=False)
            self.assertEqual(creds['token'], 'xoxc-file')


class SlackHeadersTests(unittest.TestCase):
    def test_omits_cookie_when_missing(self):
        headers = slack_headers('xoxb-bot', None)
        self.assertEqual(headers, {'Authorization': 'Bearer xoxb-bot'})

    def test_includes_cookie_when_present(self):
        headers = slack_headers('xoxc-user', 'xoxd-cookie')
        self.assertEqual(headers['Cookie'], 'd=xoxd-cookie')


if __name__ == '__main__':
    unittest.main()
