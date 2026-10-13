import json
from datetime import timedelta

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from . import camera_service as service
from .models import CameraSession, User
from .security import community_access


def body(request):
    if int(request.META.get('CONTENT_LENGTH') or 0) > service.MAX_BODY or len(request.body) > service.MAX_BODY:
        raise ValueError('上传画面过大。')
    data = json.loads(request.body)
    if not isinstance(data, dict):
        raise ValueError('请求格式不正确。')
    return data


def owned(request, camera_id):
    return CameraSession.objects.filter(pk=camera_id, user=request.community_user,
                                        browser_session=service.browser_id(request))


@never_cache
@require_POST
@community_access(api=True)
def start(request):
    try:
        data = body(request)
        if data.get('consent') is not True:
            raise ValueError('请先同意将抽样画面发送给 AI 分析。')
        name = data.get('name', '我的摄像头')
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 50:
            raise ValueError('设备名称需要 1 至 50 个字。')
        service.api_key()
    except (ValueError, UnicodeError) as exc:
        return JsonResponse({'message': '请求内容不正确。' if isinstance(exc, json.JSONDecodeError) else str(exc)}, status=400)
    except service.AnalysisError as exc:
        return JsonResponse({'message': str(exc)}, status=503)
    now = timezone.now()
    with transaction.atomic():
        User.objects.select_for_update().get(pk=request.community_user.pk)
        CameraSession.objects.filter(active=True, last_seen__lt=now - timedelta(seconds=service.TIMEOUT)).update(active=False, status='stopped')
        if CameraSession.objects.filter(user=request.community_user, active=True).count() >= 8:
            return JsonResponse({'message': '此账号已有 8 台设备开启，请先停止不用的设备。'}, status=429)
        camera = CameraSession.objects.create(user=request.community_user,
            browser_session=service.browser_id(request), name=name.strip(), last_seen=now)
    return JsonResponse({'id': str(camera.pk), 'interval': service.INTERVAL})


@never_cache
@require_POST
@community_access(api=True)
def frames(request, camera_id):
    camera = owned(request, camera_id).filter(active=True, last_seen__gte=timezone.now() - timedelta(seconds=service.TIMEOUT)).first()
    if camera is None:
        return JsonResponse({'message': '摄像头已停止或不属于当前登录，请重新开启。'}, status=404)
    try:
        images = service.validate_frames(body(request))
    except (ValueError, UnicodeError) as exc:
        return JsonResponse({'message': '上传的画面不正确。' if isinstance(exc, json.JSONDecodeError) else str(exc)}, status=400)
    if not service.submit(camera, images):
        response = JsonResponse({'message': '分析繁忙或采样太频繁，稍后自动重试。'}, status=429)
        response['Retry-After'] = str(service.INTERVAL)
        return response
    return JsonResponse({'status': 'analyzing'}, status=202)


@never_cache
@require_GET
@community_access(api=True)
def status(request, camera_id):
    camera = owned(request, camera_id).first()
    if camera is None:
        return JsonResponse({'message': '找不到当前设备。'}, status=404)
    now = timezone.now()
    if camera.last_seen < now - timedelta(seconds=service.TIMEOUT):
        owned(request, camera_id).update(active=False, status='stopped')
        camera.active, camera.status = False, 'stopped'
    elif camera.active:
        owned(request, camera_id).filter(active=True).update(last_seen=now)
        if camera.status == 'analyzing' and camera.started_at < now - timedelta(seconds=service.TIMEOUT):
            owned(request, camera_id).filter(job_id=camera.job_id, status='analyzing').update(status='error', reason='上次分析已超时，请重试。', job_id='')
            camera.status, camera.reason = 'error', '上次分析已超时，请重试。'
    return JsonResponse({'active': camera.active, 'status': camera.status, 'category': camera.category,
        'reason': camera.reason, 'completed_at': camera.completed_at.isoformat() if camera.completed_at else None})


@never_cache
@require_POST
@community_access(api=True)
def stop(request, camera_id):
    if not owned(request, camera_id).update(active=False, status='stopped', job_id=''):
        return JsonResponse({'message': '找不到当前设备。'}, status=404)
    return JsonResponse({'status': 'stopped'})
