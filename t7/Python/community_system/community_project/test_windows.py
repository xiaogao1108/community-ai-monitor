"""Run separately: python -m unittest community_project.test_windows -v.

All database, uploads and collected static files live in a temporary directory.
"""

import io
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

import django
from django.core.management import call_command
from django.test import Client, RequestFactory

from .test_production import production_environment


class WindowsDeploymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from django.conf import settings

        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        environment = production_environment()
        del environment["DB_PASSWORD"]
        environment.update({
            "DB_ENGINE": "sqlite",
            "DB_PATH": str(cls.root / "new.sqlite3"),
            "MEDIA_ROOT": str(cls.root / "media"),
            "STATIC_ROOT": str(cls.root / "static"),
        })
        with patch.dict(os.environ, environment, clear=True):
            configured = runpy.run_module("community_project.settings_windows")
        settings.configure(**{name: value for name, value in configured.items() if name.isupper()})
        django.setup()
        call_command("migrate", interactive=False, stdout=io.StringIO(), verbosity=0)
        call_command("collectstatic", interactive=False, stdout=io.StringIO(), verbosity=0)
        for directory in (cls.root / "media/video/abnormal", cls.root / "static/video/abnormal", cls.root / "media/imgs/products"):
            directory.mkdir(parents=True, exist_ok=True)
        (cls.root / "media/video/abnormal/test.mp4").write_bytes(b"private-video")
        (cls.root / "static/video/abnormal/test.mp4").write_bytes(b"must-not-bypass-login")
        (cls.root / "media/imgs/products/test.png").write_bytes(b"uploaded-image")
        (cls.root / "media/imgs/products/unsafe.svg").write_text("<svg/>", encoding="utf-8")
        from core.models import User

        cls.admin = User.objects.create(account="windows-admin", username="admin", password="unused-test-password", type="admin")

    @classmethod
    def tearDownClass(cls):
        from django.db import connections

        connections.close_all()
        cls.directory.cleanup()

    def setUp(self):
        self.client = Client(HTTP_HOST="community.example.org")

    def test_deployment_checks_and_new_database(self):
        from django.conf import settings

        call_command("check", deploy=True, fail_level="WARNING", stdout=io.StringIO())
        self.assertFalse(settings.DEBUG)
        self.assertEqual(Path(settings.DATABASES["default"]["NAME"]), self.root / "new.sqlite3")
        self.assertTrue((self.root / "new.sqlite3").is_file())

    def test_collected_static_and_image_alias(self):
        for url in ("/static/css/style.css", "/static/images/products/rice.svg",
                    "/static/css/vendor/bootstrap.min.css", "/static/js/vendor/jquery.min.js",
                    "/static/js/vendor/bootstrap.bundle.min.js", "/static/css/vendor/fontawesome/css/all.min.css",
                    "/static/css/vendor/fontawesome/webfonts/fa-solid-900.woff2"):
            with self.subTest(url=url):
                response = self.client.get(url, secure=True)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["X-Content-Type-Options"], "nosniff")
                self.assertIn("Strict-Transport-Security", response)
                response.close()
        response = self.client.get("/images/products/rice.svg", secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/static/images/products/rice.svg")

    def test_uploaded_images_are_live_and_confined(self):
        response = self.client.get("/static/imgs/products/test.png", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(b"".join(response.streaming_content), b"uploaded-image")
        response.close()
        (self.root / "media/imgs/products/later.png").write_bytes(b"new-image")
        response = self.client.get("/static/imgs/products/later.png", secure=True)
        self.assertEqual(response.status_code, 200)
        response.close()
        for path in ("products/unsafe.svg", "../video/abnormal/test.mp4", "products/test.png:stream", "products%5Ctest.png"):
            with self.subTest(path=path):
                response = self.client.get("/static/imgs/" + path, secure=True)
                self.assertEqual(response.status_code, 404)

    def test_video_aliases_keep_authentication_before_file_serving(self):
        paths = ("/media/video/abnormal/test.mp4", "/video/abnormal/test.mp4", "/static/video/abnormal/test.mp4")
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, secure=True).status_code, 401)
        session = self.client.session
        session["user_id"] = self.admin.user_id
        session.save()
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path, secure=True)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Cache-Control"], "private, no-store")
                self.assertEqual(b"".join(response.streaming_content), b"private-video")
                response.close()

    def test_csrf_cookie_and_untrusted_protocol_header(self):
        response = self.client.get("/login/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.cookies["csrftoken"]["secure"])
        for external in (b"cdn.jsdelivr.net", b"cdnjs.cloudflare.com", b"code.jquery.com"):
            self.assertNotIn(external, response.content)
        self.assertEqual(self.client.get("/health/", HTTP_X_FORWARDED_PROTO="https").status_code, 301)

    def test_waitress_trusts_only_the_local_tunnel_protocol(self):
        from django.core.wsgi import get_wsgi_application
        from waitress.proxy_headers import proxy_headers_middleware

        application = proxy_headers_middleware(
            get_wsgi_application(), trusted_proxy="127.0.0.1",
            trusted_proxy_headers={"x-forwarded-proto"}, clear_untrusted=True,
        )
        for remote, expected in (("127.0.0.1", "200"), ("192.0.2.1", "301")):
            environ = RequestFactory().get(
                "/health/", HTTP_HOST="community.example.org", HTTP_X_FORWARDED_PROTO="https",
                REMOTE_ADDR=remote,
            ).environ
            result = {}

            def start_response(status, headers, exc_info=None):
                result["status"] = status

            response = application(environ, start_response)
            try:
                b"".join(response)
            finally:
                response.close()
            with self.subTest(remote=remote):
                self.assertTrue(result["status"].startswith(expected))


if __name__ == "__main__":
    unittest.main()
