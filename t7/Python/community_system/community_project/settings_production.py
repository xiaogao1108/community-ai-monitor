"""生产安全配置；敏感值从环境变量或独立 secret 文件读取。"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .settings import *


def _required_value(name):
    value = os.environ.get(name, "")
    filename = os.environ.get(f"{name}_FILE", "")
    if value and filename:
        raise ImproperlyConfigured(f"{name} 和 {name}_FILE 只能设置一个")
    if filename:
        try:
            value = Path(filename).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ImproperlyConfigured(f"无法读取 {name}_FILE 指定的文件") from exc
    if not value:
        raise ImproperlyConfigured(f"生产环境必须设置 {name} 或 {name}_FILE")
    return value


def _required_list(name):
    values = [item.strip() for item in _required_value(name).split(",") if item.strip()]
    if not values:
        raise ImproperlyConfigured(f"{name} 不能为空")
    return values


DEBUG = False
SECRET_KEY = _required_value("DJANGO_SECRET_KEY")
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith("django-insecure-"):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY 必须是至少 50 字符的随机密钥")

ALLOWED_HOSTS = _required_list("DJANGO_ALLOWED_HOSTS")
if any("*" in host or "/" in host or host.startswith(".") for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS 必须列出具体域名或 IP，不能使用通配符或 URL")

CSRF_TRUSTED_ORIGINS = _required_list("DJANGO_CSRF_TRUSTED_ORIGINS")
if any(not origin.startswith("https://") or "*" in origin for origin in CSRF_TRUSTED_ORIGINS):
    raise ImproperlyConfigured("DJANGO_CSRF_TRUSTED_ORIGINS 必须列出具体的 HTTPS 站点来源")

DB_ENGINE = os.environ.get("DB_ENGINE", "mysql")
if DB_ENGINE == "sqlite":
    _database_path = Path(_required_value("DB_PATH"))
    if not _database_path.is_absolute() or _database_path.resolve() == (BASE_DIR / "db.sqlite3").resolve():
        raise ImproperlyConfigured("DB_PATH 必须指向独立数据库的绝对路径，不能使用原 db.sqlite3")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": _database_path,
            "CONN_MAX_AGE": 0,
            "OPTIONS": {"timeout": 20, "transaction_mode": "IMMEDIATE"},
        }
    }
elif DB_ENGINE == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ.get("DB_NAME", "community"),
            "USER": os.environ.get("DB_USER", "community"),
            "PASSWORD": _required_value("DB_PASSWORD"),
            "HOST": os.environ.get("DB_HOST", "db"),
            "PORT": os.environ.get("DB_PORT", "3306"),
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }
    if not DATABASES["default"]["USER"] or DATABASES["default"]["USER"].lower() == "root":
        raise ImproperlyConfigured("生产数据库必须使用独立应用账号，不能使用 root")
else:
    raise ImproperlyConfigured("DB_ENGINE 只能是 mysql 或 sqlite")

AI_INGEST_TOKEN = _required_value("AI_INGEST_TOKEN")
if len(AI_INGEST_TOKEN) < 32:
    raise ImproperlyConfigured("AI_INGEST_TOKEN 必须是至少 32 字符的随机令牌")

MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", "/app/t7/front/public"))
STATIC_ROOT = Path(os.environ.get("STATIC_ROOT", "/data/static"))
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

# web 容器仅接受 Docker 内网请求；公网代理负责覆盖该请求头。
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = "DENY"
