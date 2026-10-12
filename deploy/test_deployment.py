import importlib.util
from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bundle', ROOT / 'deploy' / 'build_bundle.py')
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)
config_spec = importlib.util.spec_from_file_location('init_config', ROOT / 'deploy' / 'init_config.py')
init_config = importlib.util.module_from_spec(config_spec)
config_spec.loader.exec_module(init_config)


class DeploymentTests(unittest.TestCase):
    def test_secrets_and_local_data_are_not_packaged(self):
        paths = {p.relative_to(ROOT).as_posix() for p in bundle.deployment_files(ROOT)}
        self.assertTrue(paths)
        for path in paths:
            parts = Path(path).parts
            self.assertFalse(set(parts) & bundle.EXCLUDED_PARTS, path)
            self.assertNotIn(Path(path).name, bundle.PRIVATE_NAMES)
            self.assertFalse(path.endswith(('.sqlite3', '.sql', '.mp4', '.log', '.zip')))
            self.assertNotIn('/static/video/', path)
            self.assertNotIn('/static/files/', path)
            self.assertNotIn('/static/imgs/', path)

    def test_only_https_gateway_publishes_ports(self):
        config = yaml.safe_load((ROOT / 'deploy' / 'compose.yaml').read_text(encoding='utf-8'))
        for service, values in config['services'].items():
            if service != 'proxy':
                self.assertNotIn('ports', values, service)
        self.assertEqual(config['services']['proxy']['ports'], ['80:80', '443:443'])
        self.assertEqual(config['services']['ai']['profiles'], ['ai'])
        for service in ('web', 'ai'):
            self.assertIn('healthcheck', config['services'][service])
            self.assertIn('secrets', config['services'][service])

    def test_bundle_rejects_api_key(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'deploy') as directory:
            path = Path(directory) / 'source.py'
            path.write_text('key = "' + 'sk-' + 'x' * 32 + '"', encoding='utf-8')
            with self.assertRaises(ValueError):
                bundle.checked_content(path)

    def test_required_deployment_sources_exist(self):
        for file in (
            'deploy/README.md', 'deploy/compose.yaml', 'deploy/Dockerfile.web',
            'deploy/Dockerfile.ai', 'deploy/Caddyfile', 'deploy/web-entrypoint.sh',
            't7/Python/community_system/community_project/settings_production.py',
            't7/Python/community_system/requirements.production.txt',
            't7/Python/aiWatchdog-main/requirements.production.txt',
        ):
            self.assertTrue((ROOT / file).is_file(), file)

    def test_initializer_preserves_secrets_on_second_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env.example').write_text('DOMAIN=community.example.com\n', encoding='utf-8')
            captured = io.StringIO()
            with patch.object(init_config, '__file__', str(root / 'init_config.py')), \
                    patch('sys.argv', ['init_config.py', '--domain', 'community.test']), \
                    patch.object(init_config.getpass, 'getpass', return_value='private-test-value') as prompt, \
                    redirect_stdout(captured):
                init_config.main()
                original = {file.name: file.read_bytes() for file in (root / 'secrets').iterdir()}
                init_config.main()
                current = {file.name: file.read_bytes() for file in (root / 'secrets').iterdir()}
                self.assertEqual(original, current)
                prompt.assert_called_once()
            self.assertNotIn('private-test-value', captured.getvalue())
            self.assertEqual(len(original), 5)
            self.assertTrue((root / 'input').is_dir())


if __name__ == '__main__':
    unittest.main()
