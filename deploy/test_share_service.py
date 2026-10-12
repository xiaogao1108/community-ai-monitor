import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import share_service as share
import open_public


class ShareServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.state_patch = patch.object(share, 'STATE', self.root)
        self.state_patch.start()
        self.service = share.ShareService()
        self.service.url = 'https://current.lhr.life'
        self.service.tunnel = Mock(pid=99)
        self.service.tunnel.poll.return_value = None

    def tearDown(self):
        self.state_patch.stop()
        self.directory.cleanup()

    def test_rotation_uses_latest_event_and_restarts_with_exact_domain(self):
        self.service.updates.put('https://old.lhr.life')
        self.service.updates.put('https://new.lhr.life')
        with patch.object(self.service, 'start_web') as restart:
            self.assertTrue(self.service.apply_updates())
        restart.assert_called_once_with('https://new.lhr.life')

    def test_same_domain_event_does_not_restart_web(self):
        self.service.updates.put(self.service.url)
        with patch.object(self.service, 'start_web') as restart:
            self.assertFalse(self.service.apply_updates())
        restart.assert_not_called()

    def test_three_successes_required_and_a_failure_revokes_healthy_state(self):
        result = {'ok': True, 'http_status': 200, 'checked_at': time.time()}
        for _ in range(2):
            self.service.record_check(self.service.url, result)
            self.assertEqual(self.service.state, 'checking')
        self.service.record_check(self.service.url, result)
        self.assertEqual(self.service.state, 'running')
        self.service.record_check(self.service.url, {'ok': False, 'http_status': 301})
        self.assertEqual(self.service.state, 'degraded')
        self.assertIn('尚未通过', (self.root / '公网访问地址.txt').read_text(encoding='utf-8'))

    def test_stale_health_result_cannot_certify_new_domain(self):
        self.service.record_check('https://old.lhr.life', {'ok': True})
        self.assertEqual(self.service.successes, 0)
        self.assertIsNone(self.service.check)

    def test_stopped_status_removes_shareable_url(self):
        self.service.url = None
        self.service.state = 'stopped'
        self.service.publish()
        state = json.loads((self.root / 'service.json').read_text(encoding='utf-8'))
        self.assertIsNone(state['public_url'])
        self.assertNotIn('https://', (self.root / '公网访问地址.txt').read_text(encoding='utf-8'))

    def test_health_does_not_follow_redirects_or_accept_error_html(self):
        for status in (301, 403, 502):
            with self.subTest(status=status):
                response = Mock(status_code=status)
                with patch.object(share.requests, 'get', return_value=response) as get:
                    result = share.health_check('https://current.lhr.life')
                self.assertFalse(result['ok'])
                self.assertFalse(get.call_args.kwargs['allow_redirects'])

    def test_shutdown_only_stops_owned_process_object(self):
        process = Mock()
        process.poll.return_value = None
        share.stop_process(process)
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=5)

    def test_failed_connection_clears_url_and_schedules_bounded_retry(self):
        with patch.object(share, 'open_localhost_tunnel', side_effect=RuntimeError('offline')):
            for _ in range(6):
                self.service.connect()
        self.assertEqual(self.service.state, 'reconnecting')
        self.assertIsNone(self.service.url)
        self.assertIsNone(self.service.tunnel)
        self.assertEqual(self.service.retry_delay, 30)
        self.assertGreater(self.service.retry_at, time.monotonic())

    def test_cloudflare_uses_same_supervisor_and_only_project_tool(self):
        service = share.ShareService('cloudflare')
        process = Mock()
        def connect(tool, children, flags, updates, stopped):
            self.assertEqual(tool, self.root / 'tools/cloudflared.exe')
            children.append(process)
            return 'https://test.trycloudflare.com'
        with patch.object(share, 'open_tunnel', side_effect=connect), \
                patch.object(share, 'open_localhost_tunnel') as ssh, \
                patch.object(service, 'start_web') as web:
            service.connect()
        ssh.assert_not_called()
        web.assert_called_once_with('https://test.trycloudflare.com')
        self.assertIs(service.tunnel, process)

    def test_unknown_provider_rejected(self):
        with self.assertRaises(ValueError):
            share.ShareService('unknown')

    def test_launcher_rejects_stale_failed_or_wrong_provider_checks(self):
        state = {'status': 'running', 'provider': 'cloudflare', 'updated_at': time.time(),
                 'public_url': 'https://test.trycloudflare.com',
                 'public_check': {'ok': True, 'checked_at': time.time()}}
        variants = [dict(state, status='degraded'), dict(state, updated_at=0),
                    dict(state, provider='localhost.run'),
                    dict(state, public_check={'ok': False, 'checked_at': time.time()}),
                    dict(state, public_check={'ok': True, 'checked_at': 0})]
        with patch.object(open_public, 'configuration', return_value={'provider': 'cloudflare'}), \
                patch.object(open_public.urllib.request, 'urlopen') as request:
            for variant in variants:
                with self.subTest(variant=variant), patch.object(open_public, 'service_state', return_value=variant):
                    self.assertIsNone(open_public.current_url())
        request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
