from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.views.decorators.http import require_safe
from whitenoise.middleware import WhiteNoiseMiddleware


IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


def _relative_path(path):
    relative = Path(path)
    if relative.is_absolute() or ".." in relative.parts or "\\" in path or ":" in path:
        raise Http404
    return relative


@require_safe
def uploaded_image(request, path):
    relative = _relative_path(path)
    content_type = IMAGE_TYPES.get(relative.suffix.lower())
    if content_type is None:
        raise Http404
    root = (Path(settings.MEDIA_ROOT) / "imgs").resolve()
    filename = (root / relative).resolve()
    if not filename.is_relative_to(root) or not filename.is_file():
        raise Http404
    response = FileResponse(filename.open("rb"), content_type=content_type)
    response["Cache-Control"] = "public, max-age=300"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_safe
def image_alias(request, path):
    relative = _relative_path(path)
    if relative.suffix.lower() not in {*IMAGE_TYPES, ".svg"}:
        raise Http404
    return HttpResponseRedirect("/static/images/" + quote(path, safe="/"))


class WindowsStaticMiddleware(WhiteNoiseMiddleware):
    def __call__(self, request):
        # 动态图片和受保护录像必须进入 Django 视图，不能命中静态文件缓存。
        if request.path_info.startswith(("/static/imgs/", "/static/video/")):
            return self.get_response(request)
        return super().__call__(request)
