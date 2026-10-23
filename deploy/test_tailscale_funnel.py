import unittest
import io
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

import tailscale_funnel as funnel
import share_service as share


class TailscaleFunnelTests(unittest.TestCase):
    def test_only_registered_running_device_provides_fixed_domain(self):
        state = {'BackendState': 'Running', 'Self': {'DNSName': 'community-ai-monitor.test-tail.ts.net.'}}
        self.assertEqual(funnel.public_url(state), 'https://community-ai-monitor.test-tail.ts.net')
        for name in ('', 'https://test.ts.net', 'test.ts.net.evil.example', 'a/b.test.ts.net', 'x.ts.net:443'):
            state['Self']['DNSName'] = name
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                funnel.public_url(state)
        with self.assertRaisesRegex(RuntimeError, '登录'):
            funnel.public_url({'BackendState': 'NeedsLogin'})

    def test_preexisting_https_services_are_not_overwritten(self):
        conflicts = [
            {'TCP': {'443': {'HTTPS': True}}},
            {'Web': {'example.tail.ts.net:443': {'Handlers': {'/': {'Proxy': 'http://127.0.0.1:8000'}}}}},
            {'Foreground': {'another-process': {'TCP': {'443': {'HTTPS': True}}}}},
        ]
        for config in conflicts:
            with self.subTest(config=config), patch.object(funnel, 'public_url', return_value='https://device.tail.ts.net'), \
                    patch.object(funnel, 'read_status', return_value=config):
                with self.assertRaisesRegex(RuntimeError, '覆盖'):
                    funnel.check_available()

    def test_unrelated_port_can_coexist(self):
        with patch.object(funnel, 'public_url', return_value='https://device.tail.ts.net'), \
                patch.object(funnel, 'read_status', return_value={'TCP': {'8443': {'HTTPS': True}}}):
            self.assertEqual(funnel.check_available(), 'https://device.tail.ts.net')

    def test_invalid_cli_output_is_not_a_success(self):
        for output in ('not-json', '[]'):
            with patch.object(funnel, 'executable', return_value='tailscale.exe'), \
                    patch.object(funnel.subprocess, 'run', return_value=Mock(returncode=0, stdout=output)):
                with self.assertRaises(RuntimeError):
                    funnel.read_status('status')

    def test_supervisor_owns_only_new_funnel_process(self):
        service = share.ShareService('tailscale')
        process = Mock()
        def connect(children, flags, updates, stopped):
            children.append(process)
            return 'https://device.tail.ts.net'
        with patch.object(service, 'publish'), patch.object(funnel, 'open_tunnel', side_effect=connect), \
                patch.object(service, 'start_web') as web, patch.object(share, 'open_tunnel') as cloudflare, \
                patch.object(share, 'open_localhost_tunnel') as ssh:
            service.connect()
        web.assert_called_once_with('https://device.tail.ts.net')
        self.assertIs(service.tunnel, process)
        cloudflare.assert_not_called()
        ssh.assert_not_called()

    def test_foreground_funnel_only_forwards_project_loopback_port(self):
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory)
            (state_dir / 'logs').mkdir()
            process = Mock(stdout=io.StringIO('Available on the internet:\nhttps://device.tail.ts.net/\n'))
            process.poll.return_value = None
            children = []
            with patch.object(funnel, 'STATE', state_dir), \
                    patch.object(funnel, 'check_available', return_value='https://device.tail.ts.net'), \
                    patch.object(funnel, 'executable', return_value='tailscale.exe'), \
                    patch.object(funnel.subprocess, 'Popen', return_value=process) as start:
                self.assertEqual(funnel.open_tunnel(children, 0), 'https://device.tail.ts.net')
            self.assertEqual(children, [process])
            self.assertEqual(start.call_args.args[0], ['tailscale.exe', 'funnel', '--yes', '--https=443', 'http://127.0.0.1:8765'])
            self.assertNotIn('--bg', start.call_args.args[0])

    def test_missing_login_stops_before_replacing_current_site(self):
        import open_public
        with patch.object(open_public, 'configuration', return_value={'provider': 'tailscale'}), \
                patch.object(funnel, 'public_url', side_effect=RuntimeError('needs login')), \
                patch.object(open_public, 'service_state') as state:
            with self.assertRaisesRegex(RuntimeError, 'needs login'):
                open_public.main()
            state.assert_not_called()


if __name__ == '__main__':
    unittest.main()
