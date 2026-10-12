from functools import wraps
from secrets import compare_digest

from django.conf import settings
from django.contrib.auth.hashers import check_password, identify_hasher
from django.http import JsonResponse
from django.shortcuts import redirect

from .models import User


def verify_community_password(raw_password, encoded):
    if not raw_password:
        return False
    try:
        identify_hasher(encoded)
    except ValueError:
        return settings.DEBUG and compare_digest(raw_password.encode(), encoded.encode())
    return check_password(raw_password, encoded)


def community_user(request):
    user_id = request.session.get('user_id')
    return User.objects.filter(user_id=user_id).first() if user_id else None


def community_access(*roles, api=False):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            user = community_user(request)
            if user is None:
                if api:
                    return JsonResponse({'message': '请先登录'}, status=401)
                return redirect('login')
            if roles and user.type not in roles:
                return JsonResponse({'message': '没有访问权限'}, status=403)
            request.community_user = user
            return view(request, *args, **kwargs)
        return wrapped
    return decorate


def ai_ingest_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        expected = getattr(settings, 'AI_INGEST_TOKEN', '')
        authorization = request.headers.get('Authorization', '')
        supplied = authorization[7:] if authorization.startswith('Bearer ') else ''
        if not expected or not compare_digest(supplied.encode(), expected.encode()):
            return JsonResponse({'status': 'error', 'message': '认证失败'}, status=401)
        return view(request, *args, **kwargs)
    return wrapped
