"""Run with: python -m unittest community_project.test_production -v.

Only an in-memory SQLite database is used; the existing database is never opened.
"""

import io
import os
from pathlib import Path
import runpy
import secrets
import tempfile
import unittest
from unittest.mock import patch

import django
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db import OperationalError, connection
from django.test import Client


def production_environment():
    return {
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(64),
        "DJANGO_ALLOWED_HOSTS": "community.example.org,localhost",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "https://community.example.org",
        "DB_PASSWORD": secrets.token_urlsafe(32),
        "AI_INGEST_TOKEN": secrets.token_urlsafe(32),
    }


def load_settings(environment):
    with patch.dict(os.environ, environment, clear=True):
        return runpy.run_module("community_project.settings_production")


class ProductionConfigurationTests(unittest.TestCase):
    def test_missing_secrets_cannot_fall_back_to_development_file(self):
        for name in ("DJANGO_SECRET_KEY", "DB_PASSWORD", "AI_INGEST_TOKEN"):
            environment = production_environment()
            del environment[name]
            with self.subTest(name=name), self.assertRaises(ImproperlyConfigured):
                load_settings(environment)

    def test_docker_secret_files_are_supported(self):
        environment = production_environment()
        expected = {}
        with tempfile.TemporaryDirectory() as directory:
            for name in ("DJANGO_SECRET_KEY", "DB_PASSWORD", "AI_INGEST_TOKEN"):
                expected[name] = environment.pop(name)
                filename = Path(directory) / name
                filename.write_text(expected[name] + "\n", encoding="utf-8")
                environment[f"{name}_FILE"] = str(filename)
            configured = load_settings(environment)
        self.assertEqual(configured["SECRET_KEY"], expected["DJANGO_SECRET_KEY"])
        self.assertEqual(configured["DATABASES"]["default"]["PASSWORD"], expected["DB_PASSWORD"])
        self.assertEqual(configured["AI_INGEST_TOKEN"], expected["AI_INGEST_TOKEN"])

    def test_unsafe_production_values_are_rejected(self):
        for name, value in (
            ("DJANGO_ALLOWED_HOSTS", "*"),
            ("DJANGO_ALLOWED_HOSTS", ".example.org"),
            ("DJANGO_CSRF_TRUSTED_ORIGINS", "http://community.example.org"),
            ("DJANGO_SECRET_KEY", "short"),
            ("AI_INGEST_TOKEN", "short"),
            ("DB_USER", "root"),
        ):
            environment = production_environment()
            environment[name] = value
            with self.subTest(name=name), self.assertRaises(ImproperlyConfigured):
                load_settings(environment)

    def test_sqlite_requires_an_explicit_independent_path(self):
        environment = production_environment()
        environment["DB_ENGINE"] = "sqlite"
        del environment["DB_PASSWORD"]
        original_database = Path(__file__).resolve().parent.parent / "db.sqlite3"
        for path in ("", "relative.sqlite3", str(original_database)):
            environment["DB_PATH"] = path
            with self.subTest(path=path), self.assertRaises(ImproperlyConfigured):
                load_settings(environment)
        with tempfile.TemporaryDirectory() as directory:
            environment["DB_PATH"] = str(Path(directory) / "new.sqlite3")
            configured = load_settings(environment)
            self.assertEqual(configured["DATABASES"]["default"]["ENGINE"], "django.db.backends.sqlite3")
            self.assertFalse(Path(environment["DB_PATH"]).exists())


class FreshDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from django.conf import settings

        configured = load_settings(production_environment())
        configured = {name: value for name, value in configured.items() if name.isupper()}
        configured["DATABASES"] = {
            "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
        }
        settings.configure(**configured)
        django.setup()
        call_command("migrate", interactive=False, stdout=io.StringIO(), verbosity=0)

    @classmethod
    def tearDownClass(cls):
        connection.close()

    def test_fresh_database_has_current_model_columns(self):
        from django.apps import apps

        with connection.cursor() as cursor:
            for model in apps.get_app_config("core").get_models():
                columns = {
                    column.name
                    for column in connection.introspection.get_table_description(cursor, model._meta.db_table)
                }
                with self.subTest(model=model.__name__):
                    self.assertTrue({field.column for field in model._meta.local_fields} <= columns)

    def test_production_deployment_checks(self):
        call_command("check", deploy=True, fail_level="WARNING", stdout=io.StringIO())

    def test_health_checks_database_and_avoids_error_details(self):
        client = Client(HTTP_HOST="community.example.org")
        response = client.get("/health/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        with patch("community_project.health.connection.cursor", side_effect=OperationalError("private database detail")):
            response = client.get("/health/", secure=True)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})

    def test_http_redirect_and_proxy_tls_header(self):
        client = Client(HTTP_HOST="community.example.org")
        self.assertEqual(client.get("/health/").status_code, 301)
        self.assertEqual(client.get("/health/", HTTP_X_FORWARDED_PROTO="https").status_code, 200)


if __name__ == "__main__":
    unittest.main()
