import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('windows_launcher', Path(__file__).with_name('windows.py'))
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class WindowsLauncherTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.state = Path(self.directory.name)
        self.state_patch = patch.object(launcher, 'STATE', self.state)
        self.state_patch.start()

    def tearDown(self):
        self.state_patch.stop()
        self.directory.cleanup()

    def test_configuration_keeps_secrets_on_repeat(self):
        launcher.configuration()
        secret = (self.state / 'secrets/django_secret_key.txt').read_bytes()
        launcher.configuration()
        self.assertEqual((self.state / 'secrets/django_secret_key.txt').read_bytes(), secret)
        self.assertGreaterEqual(len(secret), 50)

    def test_environment_uses_isolated_data_and_secrets(self):
        with patch.dict(os.environ, {'DJANGO_SECRET_KEY': 'inherited', 'AI_INGEST_TOKEN': 'inherited'}):
            env = launcher.environment('https://demo.trycloudflare.com')
        self.assertNotIn('DJANGO_SECRET_KEY', env)
        self.assertNotIn('AI_INGEST_TOKEN', env)
        self.assertEqual(env['DB_PATH'], str(self.state / 'data/db.sqlite3'))
        self.assertEqual(env['DJANGO_ALLOWED_HOSTS'], 'demo.trycloudflare.com,localhost,127.0.0.1')
        self.assertEqual(env['AI_HOST'], '127.0.0.1')

    def test_private_deepseek_file_takes_precedence(self):
        launcher.configuration()
        (self.state / 'secrets/deepseek_api_key.txt').write_text('test-only', encoding='utf-8')
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'inherited'}):
            env = launcher.environment()
        self.assertNotIn('DEEPSEEK_API_KEY', env)
        self.assertEqual(env['DEEPSEEK_API_KEY_FILE'], str(self.state / 'secrets/deepseek_api_key.txt'))

    def test_invalid_public_urls_rejected(self):
        for url in ('http://example.org', 'https://name:password@example.org', 'https://example.org:8765',
                    'https://example.org/path', 'https://example.org?query=1', 'https://example.org#fragment'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                launcher.environment(url)

    def test_local_configuration_is_explicit(self):
        self.assertEqual(launcher.environment(local=True)['DJANGO_SETTINGS_MODULE'], 'community_project.settings_windows_local')
        self.assertEqual(launcher.environment()['DJANGO_SETTINGS_MODULE'], 'community_project.settings_windows')

    def test_incomplete_tunnel_file_rejected(self):
        tool = self.state / 'cloudflared.exe'
        tool.write_bytes(b'MZincomplete')
        with patch.object(launcher.subprocess, 'run', side_effect=OSError('invalid executable')):
            self.assertFalse(launcher.tunnel_tool_valid(tool))

    def test_download_hash_checked_before_executing_binary(self):
        response = io.BytesIO(b'untrusted-download')
        response.headers = {'Content-Length': '18'}
        with patch.object(launcher.urllib.request, 'urlopen', return_value=response), \
                patch.object(launcher, 'tunnel_tool_valid', return_value=False) as executable_check:
            with self.assertRaisesRegex(RuntimeError, 'SHA256'):
                launcher.install_tunnel()
        executable_check.assert_called_once_with(self.state / 'tools/cloudflared.exe')

    def test_localhost_parses_only_registered_tunnel_url(self):
        event = {'type': 'v1.tcpip_forward.register.accepted',
                 'data': 'abc.lhr.life tunneled with tls termination, https://abc.lhr.life\r\nQR...'}
        self.assertEqual(launcher.localhost_url(json.dumps(event)), 'https://abc.lhr.life')
        event['data'] = 'https://abc.localhost.run\n'
        self.assertEqual(launcher.localhost_url(json.dumps(event)), 'https://abc.localhost.run')
        for line in ('https://admin.localhost.run/', '{}', '[]', 'invalid json'):
            self.assertIsNone(launcher.localhost_url(line))

    def test_cloudflare_detects_server_deleted_tunnel(self):
        self.assertEqual(launcher.cloudflare_event('ERR Register tunnel error="Unauthorized: Tunnel not found"'),
                         {'error': 'tunnel_not_found'})
        self.assertEqual(launcher.cloudflare_event('| https://example.trycloudflare.com |'),
                         'https://example.trycloudflare.com')
        for line in ('ERR dial tcp: i/o timeout', 'https://example.trycloudflare.com.evil.test'):
            self.assertIsNone(launcher.cloudflare_event(line))

    def test_localhost_rejects_unrelated_domains_and_events(self):
        for url in ('https://abc.lhr.life.evil.test', 'https://example.org', 'http://abc.lhr.life'):
            event = {'type': 'v1.tcpip_forward.register.accepted', 'data': url}
            self.assertIsNone(launcher.localhost_url(json.dumps(event)))
        self.assertIsNone(launcher.localhost_url(json.dumps({'type': 'error', 'data': 'https://abc.lhr.life'})))

    def test_localhost_command_exposes_only_project_and_isolates_ssh(self):
        with patch.object(launcher.shutil, 'which', return_value='ssh.exe'):
            command = launcher.localhost_command()
        self.assertEqual(command[command.index('-R') + 1], '80:127.0.0.1:8765')
        self.assertIn('nokey@localhost.run', command)
        self.assertIn('StrictHostKeyChecking=accept-new', command)
        self.assertIn('IdentityAgent=none', command)
        self.assertIn('PubkeyAuthentication=no', command)
        self.assertIn('--inject-http-proxy-headers', command)
        self.assertEqual(command[command.index('-F') + 1], os.devnull)
        self.assertTrue(any('localhost-run-known-hosts' in part for part in command))

    def test_missing_ssh_reports_actionable_error(self):
        with patch.object(launcher.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'OpenSSH'):
                launcher.localhost_command()


if __name__ == '__main__':
    unittest.main()
