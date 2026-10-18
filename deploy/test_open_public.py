import unittest
import tempfile
import time
from pathlib import Path
from contextlib import nullcontext
from unittest.mock import patch

import open_public


class StaleShareTests(unittest.TestCase):
    def test_recent_state_left_by_dead_service_starts_new_process(self):
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory)
            (state_dir / 'logs').mkdir()
            state = {'provider': 'cloudflare', 'status': 'running', 'updated_at': time.time(), 'session': 'test-session'}
            with patch.object(open_public, 'STATE', state_dir), \
                    patch.object(open_public, 'configuration', return_value={'provider': 'cloudflare'}), \
                    patch.object(open_public, 'tunnel_tool_valid', return_value=True), \
                    patch.object(open_public, 'current_url', side_effect=[None, 'https://test.trycloudflare.com']), \
                    patch.object(open_public, 'service_state', return_value=state), \
                    patch.object(open_public, 'share_is_stopped', return_value=True), \
                    patch.object(open_public, 'environment', return_value={}), \
                    patch.object(open_public.subprocess, 'Popen') as start, \
                    patch.object(open_public.webbrowser, 'open'), patch('builtins.print'):
                open_public.main()
                start.assert_called_once()

    def test_unlocked_and_unused_port_allows_restart(self):
        with patch.object(open_public, 'exclusive_share', return_value=nullcontext()), \
                patch.object(open_public.socket, 'socket') as socket_factory:
            self.assertTrue(open_public.share_is_stopped())
            socket_factory.return_value.__enter__.return_value.bind.assert_called_once_with(('127.0.0.1', open_public.PORT))

    def test_existing_supervisor_prevents_duplicate_start(self):
        with patch.object(open_public, 'exclusive_share', side_effect=RuntimeError('locked')), \
                patch.object(open_public.socket, 'socket') as socket_factory:
            self.assertFalse(open_public.share_is_stopped())
            socket_factory.assert_not_called()

    def test_busy_port_does_not_stop_other_process(self):
        with patch.object(open_public, 'exclusive_share', return_value=nullcontext()), \
                patch.object(open_public.socket, 'socket') as socket_factory:
            socket_factory.return_value.__enter__.return_value.bind.side_effect = OSError('in use')
            self.assertFalse(open_public.share_is_stopped())


if __name__ == '__main__':
    unittest.main()
