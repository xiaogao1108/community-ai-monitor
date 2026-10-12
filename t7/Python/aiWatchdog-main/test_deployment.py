"""部署适配的离线检查；不会访问摄像头、Django 或模型 API。"""

import asyncio
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import cv2
import httpx
import numpy as np
from fastapi.testclient import TestClient

import config
from django_integration import DjangoIntegration
import video_recording
import video_server


class ConfigurationTests(unittest.TestCase):
    def test_camera_index_and_path(self):
        self.assertEqual(config.parse_video_source('0'), 0)
        self.assertEqual(config.parse_video_source('2'), 2)
        self.assertEqual(config.parse_video_source('/input/source.mp4'), '/input/source.mp4')
        self.assertEqual(config.parse_video_source('rtsp://camera/live'), 'rtsp://camera/live')
        with self.assertRaises(ValueError):
            config.parse_video_source(' ')
        with patch.object(config, 'VIDEO_SOURCE', 'old.mp4'):
            config.update_config({'video_source': 0})
            self.assertEqual(config.VIDEO_SOURCE, 0)

    def test_secret_file_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            secret = Path(directory) / 'secret.txt'
            secret.write_text('dummy-file-token\n', encoding='utf-8')
            with patch.dict(os.environ, {'TEST_SECRET_FILE': str(secret)}, clear=True):
                self.assertEqual(config.read_secret('TEST_SECRET'), 'dummy-file-token')
                os.environ['TEST_SECRET'] = 'dummy-env-token'
                self.assertEqual(config.read_secret('TEST_SECRET'), 'dummy-env-token')
            with patch.dict(os.environ, {'TEST_SECRET_FILE': str(secret) + '.missing'}, clear=True):
                with self.assertRaises(FileNotFoundError):
                    config.read_secret('TEST_SECRET')

    def test_unavailable_source_fails_and_releases_capture(self):
        capture = MagicMock()
        capture.isOpened.return_value = False
        with patch.object(config.APIConfig, 'DEEPSEEK_API_KEY', 'test-key'), \
                patch('video_server.cv2.VideoCapture', return_value=capture):
            processor = video_server.VideoProcessor(0)
            with self.assertRaisesRegex(RuntimeError, 'VIDEO_SOURCE'):
                processor.open_source()
            capture.release.assert_called_once()

    def test_missing_key_does_not_open_source(self):
        with patch.object(config.APIConfig, 'DEEPSEEK_API_KEY', ''), \
                patch('video_server.cv2.VideoCapture') as capture:
            with self.assertRaisesRegex(RuntimeError, 'DEEPSEEK_API_KEY'):
                video_server.VideoProcessor(0).open_source()
            capture.assert_not_called()


class ProcessingTests(unittest.IsolatedAsyncioTestCase):
    async def test_short_file_completes_once_without_looping_or_real_api(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = str(Path(directory) / 'source.mp4')
            writer = cv2.VideoWriter(filename, cv2.VideoWriter_fourcc(*'mp4v'), 25.0, (32, 32))
            self.assertTrue(writer.isOpened())
            for level in (0, 50, 100):
                writer.write(np.full((32, 32, 3), level, dtype=np.uint8))
            writer.release()
            analyzer = MagicMock()
            analyzer.analyze = AsyncMock(return_value={'alert': '无异常'})
            with patch.object(config.APIConfig, 'DEEPSEEK_API_KEY', 'test-key'), \
                    patch('video_server.MultiModalAnalyzer', return_value=analyzer), \
                    patch('video_server.VideoArchiver') as archiver:
                processor = video_server.VideoProcessor(filename)
                await asyncio.to_thread(processor.open_source)
                await processor.start_processing()
                self.assertEqual(processor.frames_read, 3)
                self.assertEqual(processor.state, 'completed')
                self.assertTrue(processor.health()['healthy'])
                self.assertFalse(processor.cap.isOpened())
                analyzer.analyze.assert_awaited_once()
                self.assertEqual(archiver.return_value.write_frame.call_count, 3)
                archiver.return_value.close.assert_called_once()

    async def test_analysis_failure_is_unhealthy_then_recovers(self):
        processor = video_server.VideoProcessor(0)
        processor.state = 'running'
        processor.buffer.append({'frame': np.zeros((16, 16, 3), dtype=np.uint8), 'timestamp': '2026-10-11-10-00-00'})
        processor.analyzer = MagicMock()
        processor.analyzer.analyze = AsyncMock(side_effect=RuntimeError('private diagnostic'))
        with self.assertLogs(level='ERROR'):
            await processor.trigger_analysis()
        self.assertFalse(processor.health()['healthy'])
        self.assertNotIn('private diagnostic', processor.health()['error'])
        processor.analyzer.analyze = AsyncMock(return_value={'alert': '无异常'})
        await processor.trigger_analysis()
        self.assertTrue(processor.health()['healthy'])

    async def test_live_stream_disconnect_is_failed_not_completed(self):
        processor = video_server.VideoProcessor(0)
        processor._running = True
        processor.state = 'running'
        processor.cap = MagicMock()
        processor.cap.read.return_value = (False, None)
        await processor.start_processing()
        self.assertEqual(processor.state, 'failed')
        self.assertFalse(processor.health()['healthy'])

    async def test_health_endpoint_reports_failed_and_completed(self):
        processor = video_server.VideoProcessor(0)
        with patch.object(video_server.app.state, 'processor', processor, create=True):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=video_server.app), base_url='http://ai') as client:
                processor.state = 'failed'
                self.assertEqual((await client.get('/health/')).status_code, 503)
                processor.state = 'completed'
                result = await client.get('/health/')
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json()['status'], 'completed')

    async def test_django_bearer_and_forwarded_https_headers(self):
        def handler(request):
            self.assertEqual(request.headers.get('X-Forwarded-Proto'), 'https')
            self.assertEqual(request.headers.get('Authorization'), 'Bearer test-ingest-token')
            self.assertEqual(request.url.path, '/api/ai/abnormal/')
            self.assertEqual(json.loads(request.content)['abnormal_type'], '测试异常')
            return httpx.Response(200, json={'success': True})

        client_class = httpx.AsyncClient
        def client_factory(*args, **kwargs):
            return client_class(*args, transport=httpx.MockTransport(handler), **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            secret = Path(directory) / 'token.txt'
            secret.write_text('test-ingest-token', encoding='utf-8')
            with patch.dict(os.environ, {'AI_INGEST_TOKEN_FILE': str(secret)}, clear=True), \
                    patch('django_integration.httpx.AsyncClient', side_effect=client_factory):
                integration = DjangoIntegration()
                try:
                    self.assertTrue(await integration.send_abnormal_detection({'abnormal_type': '测试异常'}))
                finally:
                    await integration.close()


class RecordingTests(unittest.TestCase):
    def test_codec_fallback_is_transcoded_for_browser_playback(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / 'clip.mp4'
            filename.write_bytes(b'initial')
            unsupported, supported = MagicMock(), MagicMock()
            unsupported.isOpened.return_value = False
            supported.isOpened.return_value = True
            with patch('video_recording.cv2.VideoWriter', side_effect=[unsupported, supported]):
                writer, codec = video_recording.open_video_writer(filename, 1.0, (32, 32))
            self.assertEqual(codec, 'mp4v')
            unsupported.release.assert_called_once()

            def convert(command, **kwargs):
                self.assertIn('libx264', command)
                self.assertIn('+faststart', command)
                Path(command[-1]).write_bytes(b'h264-result')

            with patch('video_recording.shutil.which', return_value='ffmpeg'), \
                    patch('video_recording.subprocess.run', side_effect=convert):
                video_recording.finalize_video(writer, filename, codec, browser_playable=True)
            self.assertEqual(filename.read_bytes(), b'h264-result')
            supported.release.assert_called_once()

    def test_no_encoder_fails_instead_of_silently_dropping_video(self):
        writer = MagicMock()
        writer.isOpened.return_value = False
        with tempfile.TemporaryDirectory() as directory, \
                patch('video_recording.cv2.VideoWriter', return_value=writer):
            with self.assertRaisesRegex(RuntimeError, '无法创建录像'):
                video_recording.open_video_writer(Path(directory) / 'clip.mp4', 1.0, (32, 32))
        with patch('video_recording.shutil.which', return_value=None), \
                patch.dict('sys.modules', {'imageio_ffmpeg': None}):
            with self.assertRaisesRegex(RuntimeError, 'FFmpeg'):
                video_recording.finalize_video(writer, 'unused.mp4', 'mp4v', browser_playable=True)


class LifecycleTests(unittest.TestCase):
    def test_startup_serves_health_and_shutdown_closes_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = str(Path(directory) / 'source.mp4')
            writer = cv2.VideoWriter(filename, cv2.VideoWriter_fourcc(*'mp4v'), 25.0, (32, 32))
            self.assertTrue(writer.isOpened())
            for _ in range(3):
                writer.write(np.zeros((32, 32, 3), dtype=np.uint8))
            writer.release()
            analyzer = MagicMock()
            analyzer.analyze = AsyncMock(return_value={'alert': '无异常'})
            handler = {'filename': str(Path(directory) / 'code.log')}
            with patch.object(config, 'VIDEO_SOURCE', filename), \
                    patch.object(config.APIConfig, 'DEEPSEEK_API_KEY', 'test-key'), \
                    patch.object(config, 'ensure_directories'), \
                    patch.dict(video_server.LOG_CONFIG, {'handlers': [handler]}), \
                    patch('video_server.MultiModalAnalyzer', return_value=analyzer), \
                    patch('video_server.VideoArchiver'), \
                    patch('video_server.django_integration.close', new_callable=AsyncMock) as close:
                with TestClient(video_server.app) as client:
                    for _ in range(50):
                        response = client.get('/health/')
                        self.assertEqual(response.status_code, 200)
                        if response.json()['status'] == 'completed':
                            break
                        time.sleep(0.02)
                    self.assertEqual(response.json()['status'], 'completed')
                    self.assertNotIn(filename, response.text)
                close.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
