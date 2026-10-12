from pathlib import Path

from django.conf import settings
from django.http import Http404, JsonResponse
from django.views.static import serve

from .models import ReportVideo
from .security import community_access


@community_access(api=True)
def protected_media(request, path):
    relative = Path(path)
    if relative.is_absolute() or '..' in relative.parts or '\\' in path:
        raise Http404
    if not path.startswith('video/'):
        raise Http404
    if relative.suffix.lower() not in {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.jpg'}:
        raise Http404

    if request.community_user.type not in ('admin', 'staff'):
        urls = ['/' + path, '/static/' + path, '/media/' + path]
        if not path.startswith('video/report/') or not ReportVideo.objects.filter(
            report__reporter=request.community_user, video_url__in=urls,
        ).exists():
            return JsonResponse({'message': '没有访问权限'}, status=403)

    roots = [Path(settings.MEDIA_ROOT)]
    if settings.DEBUG:
        roots.extend(Path(root) for root in getattr(settings, 'STATICFILES_DIRS', []))
    for root in roots:
        candidate = (root / relative).resolve()
        if candidate.is_relative_to(root.resolve()) and candidate.is_file():
            response = serve(request, path, document_root=root)
            response['Cache-Control'] = 'private, no-store'
            response['X-Content-Type-Options'] = 'nosniff'
            return response
    raise Http404


def protected_video(request, path):
    return protected_media(request, 'video/' + path)
