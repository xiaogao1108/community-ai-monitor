"""只在 127.0.0.1 上使用 HTTP 的本机预览，公网入口使用 settings_windows。"""

from .settings_windows import *

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
CSRF_TRUSTED_ORIGINS = ['http://127.0.0.1:8765', 'http://localhost:8765']
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
