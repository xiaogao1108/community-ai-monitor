import io
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.hashers import check_password, make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from PIL import Image

from .file_upload_views import validate_image_file
from .models import AbnormalRecord, Product, Report, ReportVideo, User


class DeploymentSecurityTests(TestCase):
    def setUp(self):
        self.resident = User.objects.create(
            username='住户', account='resident01', password=make_password('test-only-pass'), type='resident',
        )
        self.admin = User.objects.create(
            username='管理员', account='admin001', password=make_password('test-only-pass'), type='admin',
        )

    def login_as(self, user, client=None):
        client = client or self.client
        session = client.session
        session['user_id'] = user.user_id
        session.save()

    def test_product_changes_require_current_admin_role(self):
        endpoint = '/api/products/add/'
        payload = {'productName': '商品', 'pointsRequired': 1, 'quantity': 1}
        self.assertEqual(self.client.post(endpoint, payload, content_type='application/json').status_code, 401)
        self.login_as(self.resident)
        session = self.client.session
        session['user_type'] = 'admin'
        session.save()
        self.assertEqual(self.client.post(endpoint, payload, content_type='application/json').status_code, 403)
        self.assertFalse(Product.objects.exists())
        self.login_as(self.admin)
        self.assertEqual(self.client.post(endpoint, payload, content_type='application/json').json()['state'], 2001)

    def test_csrf_enforced_for_browser_writes(self):
        client = Client(enforce_csrf_checks=True)
        self.login_as(self.admin, client)
        for url in ['/api/create-order/', '/api/products/add/', '/api/files/upload/']:
            self.assertEqual(client.post(url, '{}', content_type='application/json').status_code, 403)
        page = client.get('/products/')
        token = client.cookies['csrftoken'].value
        self.assertContains(page, 'X-CSRFToken')
        response = client.post('/api/products/add/', {
            'productName': '商品', 'pointsRequired': 1,
        }, content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.json()['state'], 2001)

    @override_settings(AI_INGEST_TOKEN='isolated-test-token')
    def test_ai_requires_bearer_and_accepts_service_without_csrf(self):
        client = Client(enforce_csrf_checks=True)
        for token in ['', 'Bearer wrong']:
            response = client.post('/api/ai/abnormal/', {}, content_type='application/json', HTTP_AUTHORIZATION=token)
            self.assertEqual(response.status_code, 401)
        self.assertFalse(AbnormalRecord.objects.exists())
        response = client.post('/api/ai/abnormal/', {'reason': 'test'}, content_type='application/json',
                               HTTP_AUTHORIZATION='Bearer isolated-test-token')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AbnormalRecord.objects.count(), 1)
        response = client.post('/api/ai/abnormal/video/upload/', {
            'video': SimpleUploadedFile('bad.html', b'<script>'), 'abnormal_id': response.json()['abnormal_id'],
        }, HTTP_AUTHORIZATION='Bearer isolated-test-token')
        self.assertEqual(response.status_code, 400)

    @override_settings(AI_INGEST_TOKEN='')
    def test_missing_ai_token_fails_closed(self):
        self.assertEqual(self.client.post('/api/ai/abnormal/').status_code, 401)
        self.assertEqual(self.client.post('/api/ai/abnormal/video/upload/').status_code, 401)

    @override_settings(AI_INGEST_TOKEN='isolated-test-token')
    def test_long_ai_title_preserves_full_message(self):
        title = '检测到异常行为，需人工核实。' * 20
        response = self.client.post('/api/ai/abnormal/', {
            'abnormal_type': title, 'reason': '原始详情',
        }, content_type='application/json', HTTP_AUTHORIZATION='Bearer isolated-test-token')
        self.assertEqual(response.status_code, 200)
        record = AbnormalRecord.objects.get()
        self.assertEqual(record.abnormal_type, title[:50])
        self.assertIn(title, record.reason)
        self.assertIn('原始详情', record.reason)

    @override_settings(AI_INGEST_TOKEN='isolated-test-token')
    def test_failed_ai_video_record_rolls_back_abnormal(self):
        with patch('core.abnormal_views.AbnormalVideo.objects.create', side_effect=ValueError('invalid video')):
            response = self.client.post('/api/ai/abnormal/', {
                'video_url': '/video/abnormal/test.mp4',
            }, content_type='application/json', HTTP_AUTHORIZATION='Bearer isolated-test-token')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(AbnormalRecord.objects.exists())

    def test_images_verified_and_general_upload_denied(self):
        image_bytes = io.BytesIO()
        Image.new('RGB', (2, 2)).save(image_bytes, format='PNG')
        valid = SimpleUploadedFile('valid.png', image_bytes.getvalue())
        self.assertTrue(validate_image_file(valid)[0])
        self.assertFalse(validate_image_file(SimpleUploadedFile('bad.png', b'<script>'))[0])
        self.assertFalse(validate_image_file(SimpleUploadedFile('bad.svg', b'<svg/>'))[0])
        self.assertEqual(self.client.post('/api/files/upload/').status_code, 401)
        self.login_as(self.resident)
        self.assertEqual(self.client.post('/api/files/upload/', {
            'file': SimpleUploadedFile('bad.html', b'<script>'), 'type': 'general',
        }).status_code, 400)
        self.assertEqual(self.client.post('/api/files/upload/', {
            'file': valid, 'type': 'product',
        }).status_code, 403)

    def test_monitoring_and_alerts_require_staff(self):
        self.assertEqual(self.client.get('/monitoring/').status_code, 302)
        self.assertEqual(self.client.get('/api/alerts/latest/').status_code, 401)
        self.login_as(self.resident)
        for url in ['/monitoring/', '/abnormal-records/', '/abnormal-records/1/', '/api/alerts/latest/']:
            self.assertEqual(self.client.get(url).status_code, 403)
        self.login_as(self.admin)
        self.assertEqual(self.client.get('/monitoring/').status_code, 200)
        self.assertEqual(self.client.post('/camera/').status_code, 410)

    @override_settings(DEBUG=False)
    def test_private_video_owner_and_aliases(self):
        with tempfile.TemporaryDirectory() as directory, self.settings(MEDIA_ROOT=directory):
            report = Report.objects.create(reporter=self.resident, report_type='test', reason='test')
            ReportVideo.objects.create(report=report, video_url='/video/report/own.mp4')
            for name in ['video/report/own.mp4', 'video/report/other.mp4', 'video/abnormal/alert.mp4']:
                file = Path(directory, name)
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(b'test video')
            self.assertEqual(self.client.get('/media/video/report/own.mp4').status_code, 401)
            self.login_as(self.resident)
            for prefix in ['/media/', '/', '/static/']:
                response = self.client.get(prefix + 'video/report/own.mp4')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['Cache-Control'], 'private, no-store')
                response.close()
            self.assertEqual(self.client.get('/media/video/report/other.mp4').status_code, 403)
            self.assertEqual(self.client.get('/media/video/abnormal/alert.mp4').status_code, 403)
            self.assertEqual(self.client.get('/media/video/../secret.txt').status_code, 404)
            self.login_as(self.admin)
            response = self.client.get('/media/video/abnormal/alert.mp4')
            self.assertEqual(response.status_code, 200)
            response.close()

    @override_settings(DEBUG=False)
    def test_new_registration_uses_hash_and_logs_in(self):
        response = self.client.post('/register/', {
            'username': '新用户', 'account': 'newuser01', 'password': 'Highly-Unique-Password!43',
        })
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(account='newuser01')
        self.assertTrue(check_password('Highly-Unique-Password!43', user.password))
        self.assertLessEqual(len(user.password), User._meta.get_field('password').max_length)
        response = self.client.post('/login/', {'account': user.account, 'password': 'Highly-Unique-Password!43'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session['user_id'], user.user_id)

    def test_legacy_password_compatibility_and_explicit_conversion(self):
        self.resident.password = 'legacy-example'
        self.resident.save(update_fields=['password'])
        with self.settings(DEBUG=False):
            self.client.post('/login/', {'account': self.resident.account, 'password': 'legacy-example'})
            self.assertNotIn('user_id', self.client.session)
        with self.settings(DEBUG=True):
            self.client.post('/login/', {'account': self.resident.account, 'password': 'legacy-example'})
            self.assertEqual(self.client.session['user_id'], self.resident.user_id)
        call_command('hash_community_passwords', stdout=io.StringIO())
        self.resident.refresh_from_db()
        self.assertEqual(self.resident.password, 'legacy-example')
        call_command('hash_community_passwords', apply=True, stdout=io.StringIO())
        self.resident.refresh_from_db()
        self.assertTrue(check_password('legacy-example', self.resident.password))
        first_hash = self.resident.password
        call_command('hash_community_passwords', apply=True, stdout=io.StringIO())
        self.resident.refresh_from_db()
        self.assertEqual(first_hash, self.resident.password)
