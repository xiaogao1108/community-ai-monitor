import base64
import json
import unittest
from unittest.mock import patch

import cv2
import httpx
import numpy as np

from config import APIConfig
from utility import chat_request, video_chat_async, video_chat_async_limit_frame


class DeepSeekTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.key_patch = patch.object(APIConfig, 'DEEPSEEK_API_KEY', 'test-key')
        self.key_patch.start()
        self.addCleanup(self.key_patch.stop)

    def mock_client(self, handler):
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        return patch('utility.httpx.AsyncClient', return_value=client)

    async def test_text_request(self):
        def handler(request):
            self.assertEqual(str(request.url), 'https://api.deepseek.com/chat/completions')
            self.assertEqual(request.headers['Authorization'], 'Bearer test-key')
            data = json.loads(request.content)
            self.assertEqual(data['model'], APIConfig.DEEPSEEK_MODEL)
            self.assertEqual(data['messages'][0]['content'], '检查异常')
            self.assertFalse(data['stream'])
            self.assertNotIn('top_k', data)
            self.assertNotIn('repetition_penalty', data)
            return httpx.Response(200, json={'choices': [{'message': {'content': '无异常状况。'}}]})

        with self.mock_client(handler):
            self.assertEqual(await chat_request('检查异常'), '无异常状况。')

    async def test_both_video_entries_send_images_and_preserve_archive(self):
        frames = [np.full((16, 16, 3), level, dtype=np.uint8) for level in (0, 255)]

        def handler(request):
            content = json.loads(request.content)['messages'][0]['content']
            self.assertEqual(content[0], {'type': 'text', 'text': '描述画面'})
            self.assertEqual(len(content), 3)
            for item, expected in zip(content[1:], (0, 255)):
                self.assertEqual(item['type'], 'image_url')
                prefix, encoded = item['image_url']['url'].split(',', 1)
                self.assertEqual(prefix, 'data:image/jpeg;base64')
                decoded = cv2.imdecode(np.frombuffer(base64.b64decode(encoded), dtype=np.uint8), cv2.IMREAD_COLOR)
                self.assertAlmostEqual(float(decoded.mean()), expected, delta=2)
            return httpx.Response(200, json={'choices': [{'message': {'content': '画面描述'}}]})

        for entry in (video_chat_async, video_chat_async_limit_frame):
            with self.mock_client(handler), patch('utility.frames_to_base64') as archive:
                self.assertEqual(await entry('描述画面', frames, None), '画面描述')
                archive.assert_called_once_with(frames, 20, None)

    async def test_missing_key_and_empty_frames_do_not_send_requests(self):
        with patch('utility.httpx.AsyncClient') as client:
            with patch.object(APIConfig, 'DEEPSEEK_API_KEY', ''):
                with self.assertRaisesRegex(ValueError, 'DEEPSEEK_API_KEY'):
                    await chat_request('检查')
            with self.assertRaisesRegex(ValueError, '视频帧'):
                await video_chat_async_limit_frame('检查', [], None)
            client.assert_not_called()

    async def test_http_error_is_not_an_alert(self):
        with self.mock_client(lambda request: httpx.Response(401, json={'error': 'unauthorized'})):
            with self.assertRaises(httpx.HTTPStatusError):
                await chat_request('检查')

    async def test_invalid_or_empty_response_is_not_an_alert(self):
        for body in ({}, {'choices': []}, {'choices': [{'message': {'content': ''}}]}):
            with self.mock_client(lambda request: httpx.Response(200, json=body)):
                with self.assertRaises(ValueError):
                    await chat_request('检查')

    async def test_stream_is_rejected_before_request(self):
        with patch('utility.httpx.AsyncClient') as client:
            with self.assertRaisesRegex(ValueError, '流式'):
                await chat_request('检查', stream=True)
            client.assert_not_called()


if __name__ == '__main__':
    unittest.main()
