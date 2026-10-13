import base64
import io
import json
import threading
from datetime import timedelta
from unittest.mock import Mock, patch

import requests
from PIL import Image
from django.test import Client, TestCase, SimpleTestCase
from django.utils import timezone

from . import camera_service as service
from .models import AbnormalRecord, CameraSession, User


def jpeg(size=(32, 24)):
    output = io.BytesIO()
    Image.new('RGB', size, 'grey').save(output, 'JPEG')
    return 'data:image/jpeg;base64,' + base64.b64encode(output.getvalue()).decode()


class CameraTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='住户', account='camera01', password='unused', type='resident')
        self.other = User.objects.create(username='其他住户', account='camera02', password='unused', type='resident')
        self.login(self.client, self.user)
        self.key = patch('core.camera_service.api_key', return_value='test-only-key')
        self.key.start()
        self.addCleanup(self.key.stop)

    def login(self, client, user):
        session = client.session
        session['user_id'] = user.pk
        session.save()

    def start(self, client=None):
        response = (client or self.client).post('/api/cameras/start/',
            {'consent': True, 'name': '客厅'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        return response.json()['id']

    def url(self, camera_id, action):
        return f'/api/cameras/{camera_id}/{action}/'

    def test_requires_login_consent_and_csrf(self):
        self.assertEqual(Client().post('/api/cameras/start/').status_code, 401)
        self.assertEqual(self.client.post('/api/cameras/start/', {'consent': False}, content_type='application/json').status_code, 400)
        csrf_client = Client(enforce_csrf_checks=True)
        self.login(csrf_client, self.user)
        page = csrf_client.get('/monitoring/')
        self.assertContains(page, '开启摄像头并分析')
        self.assertEqual(csrf_client.post('/api/cameras/start/', {}).status_code, 403)
        camera_id = self.start()
        for action in ['frames', 'stop']:
            self.assertEqual(csrf_client.post(self.url(camera_id, action), {}).status_code, 403)
        self.assertEqual(self.client.get('/api/alerts/latest/').status_code, 403)
        self.assertEqual(self.client.get('/abnormal-records/').status_code, 403)

    def test_device_and_user_isolation(self):
        first, second = self.start(), self.start()
        self.assertNotEqual(first, second)
        for user in (self.user, self.other):
            other = Client()
            self.login(other, user)
            self.assertEqual(other.get(self.url(first, 'status')).status_code, 404)
            self.assertEqual(other.post(self.url(first, 'stop')).status_code, 404)
            self.assertEqual(other.post(self.url(first, 'frames')).status_code, 404)
        response = self.client.get(self.url(first, 'status'))
        self.assertIn('no-store', response['Cache-Control'])

    def test_bad_payloads_and_session_limit(self):
        for payload in ['[]', 'null', '{', json.dumps({'consent': True, 'name': 1})]:
            self.assertEqual(self.client.post('/api/cameras/start/', payload, content_type='application/json').status_code, 400)
        camera_id = self.start()
        for payload in [{'frames': []}, {'frames': ['data:image/jpeg;base64,bad!']}, {'frames': [jpeg((1000, 24))]}]:
            self.assertEqual(self.client.post(self.url(camera_id, 'frames'), payload, content_type='application/json').status_code, 400)
        oversized = json.dumps({'frames': ['x' * service.MAX_BODY]})
        self.assertEqual(self.client.post(self.url(camera_id, 'frames'), oversized, content_type='application/json').status_code, 400)
        for _ in range(7):
            self.start()
        self.assertEqual(self.client.post('/api/cameras/start/', {'consent': True, 'name': '超额'}, content_type='application/json').status_code, 429)

    def test_background_submit_is_throttled_and_bounded(self):
        camera_id = self.start()
        slots = threading.BoundedSemaphore(1)
        with patch.object(service, '_slots', slots), patch.object(service._executor, 'submit') as submit:
            response = self.client.post(self.url(camera_id, 'frames'), {'frames': [jpeg()]}, content_type='application/json')
            self.assertEqual(response.status_code, 202)
            submit.assert_called_once()
            self.assertEqual(self.client.post(self.url(camera_id, 'frames'), {'frames': [jpeg()]}, content_type='application/json').status_code, 429)
            slots.release()
            camera = CameraSession.objects.get(pk=camera_id)
            self.assertFalse(service.submit(camera, [jpeg()]))
            self.assertTrue(slots.acquire(False))
            slots.release()

    def test_alert_persist_cooldown_and_device_separation(self):
        first, second = self.start(), self.start()
        CameraSession.objects.filter(pk__in=[first, second]).update(job_id='test-job')
        fire = {'alert': True, 'category': 'fire', 'reason': '疑似明火'}
        service.save_result(first, 'test-job', result=fire)
        service.save_result(first, 'test-job', result=fire)
        self.assertEqual(AbnormalRecord.objects.count(), 1)
        self.assertEqual(CameraSession.objects.get(pk=second).status, 'ready')
        service.save_result(second, 'test-job', result=fire)
        self.assertEqual(AbnormalRecord.objects.count(), 2)
        self.assertIn(str(first)[:8], AbnormalRecord.objects.first().reason)
        service.save_result(first, 'test-job', result={'alert': True, 'category': 'smoke', 'reason': '疑似浓烟'})
        self.assertEqual(AbnormalRecord.objects.count(), 3)

    def test_stop_expiry_and_old_jobs_cannot_create_alert(self):
        camera_id = self.start()
        CameraSession.objects.filter(pk=camera_id).update(job_id='new-job')
        fire = {'alert': True, 'category': 'fire', 'reason': '疑似明火'}
        service.save_result(camera_id, 'old-job', result=fire)
        self.assertFalse(AbnormalRecord.objects.exists())
        self.client.post(self.url(camera_id, 'stop'))
        service.save_result(camera_id, 'new-job', result=fire)
        self.assertFalse(AbnormalRecord.objects.exists())
        self.assertEqual(self.client.post(self.url(camera_id, 'frames'), {'frames': [jpeg()]}, content_type='application/json').status_code, 404)
        CameraSession.objects.filter(pk=camera_id).update(active=True, job_id='new-job', last_seen=timezone.now() - timedelta(seconds=121))
        service.save_result(camera_id, 'new-job', result=fire)
        self.assertFalse(AbnormalRecord.objects.exists())
        self.assertFalse(self.client.get(self.url(camera_id, 'status')).json()['active'])

    def test_logout_stops_current_browser_cameras_only(self):
        own = self.start()
        other = Client()
        self.login(other, self.user)
        remote = self.start(other)
        self.client.get('/logout/')
        self.assertFalse(CameraSession.objects.get(pk=own).active)
        self.assertTrue(CameraSession.objects.get(pk=remote).active)

    def test_failure_is_not_normal_result_and_stale_job_recovers(self):
        camera_id = self.start()
        CameraSession.objects.filter(pk=camera_id).update(job_id='job')
        service.save_result(camera_id, 'job', error='模型连接失败')
        result = self.client.get(self.url(camera_id, 'status')).json()
        self.assertEqual(result['status'], 'error')
        self.assertFalse(AbnormalRecord.objects.exists())
        CameraSession.objects.filter(pk=camera_id).update(status='analyzing', started_at=timezone.now() - timedelta(seconds=121))
        self.assertEqual(self.client.get(self.url(camera_id, 'status')).json()['status'], 'error')
        self.assertEqual(CameraSession.objects.get(pk=camera_id).job_id, '')


class ModelResponseTests(SimpleTestCase):
    @patch('core.camera_service.api_key', return_value='test-only-key')
    @patch('core.camera_service.requests.post')
    def test_model_request_and_validated_results(self, post, key):
        post.return_value = Mock(status_code=200)
        valid = {'alert': True, 'category': 'fire', 'reason': '疑似明火'}
        post.return_value.json.return_value = {'choices': [{'message': {'content': json.dumps(valid)}}]}
        self.assertEqual(service.analyze_frames([jpeg()]), valid)
        self.assertEqual(post.call_args.kwargs['json']['messages'][1]['content'][1]['type'], 'image_url')
        for invalid in [{'alert': 'true', 'category': 'fire', 'reason': 'x'}, {'alert': False, 'category': 'fire', 'reason': 'x'}, {}]:
            post.return_value.json.return_value = {'choices': [{'message': {'content': json.dumps(invalid)}}]}
            with self.assertRaises(service.AnalysisError):
                service.analyze_frames([jpeg()])
        for code in [401, 402, 429, 500]:
            post.return_value.status_code = code
            with self.assertRaises(service.AnalysisError):
                service.analyze_frames([jpeg()])
        post.side_effect = requests.Timeout('do not expose response or credentials')
        with self.assertRaisesRegex(service.AnalysisError, '超时或失败'):
            service.analyze_frames([jpeg()])
