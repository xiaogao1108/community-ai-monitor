"""Windows 本机服务配置，使用独立 SQLite、媒体和静态文件目录。"""

from .settings_production import *
from .settings_production import _required_value


if DB_ENGINE != "sqlite":
    raise ImproperlyConfigured("Windows 部署必须显式设置 DB_ENGINE=sqlite")

MEDIA_ROOT = Path(_required_value("MEDIA_ROOT"))
STATIC_ROOT = Path(_required_value("STATIC_ROOT"))
if not MEDIA_ROOT.is_absolute() or not STATIC_ROOT.is_absolute():
    raise ImproperlyConfigured("MEDIA_ROOT 和 STATIC_ROOT 必须是绝对路径")
if MEDIA_ROOT.resolve().is_relative_to(STATIC_ROOT.resolve()) or STATIC_ROOT.resolve().is_relative_to(MEDIA_ROOT.resolve()):
    raise ImproperlyConfigured("媒体目录和静态目录不能相同或互相包含")
if Path(DATABASES["default"]["NAME"]).resolve().is_relative_to(STATIC_ROOT.resolve()):
    raise ImproperlyConfigured("数据库不能保存在公开静态目录内")

ROOT_URLCONF = "community_project.urls_windows"
MIDDLEWARE = list(MIDDLEWARE)
MIDDLEWARE.insert(1, "community_project.windows_media.WindowsStaticMiddleware")
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# Waitress 仅信任来自本机隧道的协议头；由它生成 wsgi.url_scheme。
SECURE_PROXY_SSL_HEADER = None
