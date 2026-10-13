from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
from datetime import datetime
import json
import os
from .security import community_access, verify_community_password

from .models import (
    User, Feedback, Product, Order, Report, ReportVideo,
    AbnormalRecord, AbnormalVideo, Announcement, FeedbackProcessing,
    ReportProcessing, AbnormalProcessing
)


def home(request):
    """首页"""
    latest_announcements = Announcement.objects.filter(
        status='finalized'
    ).order_by('-created_at')[:5]
    
    popular_products = Product.objects.order_by('-points_required')[:6]
    
    context = {
        'announcements': latest_announcements,
        'products': popular_products,
    }
    return render(request, 'core/home.html', context)


def user_login(request):
    """用户登录"""
    if request.method == 'POST':
        account = request.POST.get('account')
        password = request.POST.get('password')
        
        try:
            user = User.objects.get(account=account)
            if not verify_community_password(password, user.password):
                raise User.DoesNotExist
            request.session.cycle_key()
            request.session['user_id'] = user.user_id
            request.session['username'] = user.username
            request.session['user_type'] = user.type
            messages.success(request, f'欢迎 {user.username}!')
            return redirect('home')
        except User.DoesNotExist:
            messages.error(request, '账号或密码错误')
    
    return render(request, 'core/login.html')


def user_register(request):
    """用户注册"""
    if request.method == 'POST':
        username = request.POST.get('username')
        account = request.POST.get('account')
        password = request.POST.get('password')
        nickname = request.POST.get('nickname')
        age = request.POST.get('age')
        email = request.POST.get('email')
        phone = request.POST.get('phone')

        try:
            validate_password(password)
        except ValidationError as error:
            messages.error(request, '；'.join(error.messages))
            return render(request, 'core/register.html')
        
        if User.objects.filter(account=account).exists():
            messages.error(request, '账号已存在')
            return render(request, 'core/register.html')
        
        user = User.objects.create(
            username=username,
            account=account,
            password=make_password(password),
            nickname=nickname,
            age=int(age) if age else None,
            email=email,
            phone=phone,
            type='resident'
        )
        
        messages.success(request, '注册成功，请登录')
        return redirect('login')
    
    return render(request, 'core/register.html')


def user_logout(request):
    """用户登出"""
    if request.session.session_key:
        from .camera_service import browser_id
        from .models import CameraSession
        CameraSession.objects.filter(browser_session=browser_id(request)).update(active=False, status='stopped', job_id='')
    request.session.flush()
    messages.success(request, '已成功登出')
    return redirect('home')


def user_profile(request):
    """用户个人资料"""
    if 'user_id' not in request.session:
        return redirect('login')
    
    user = get_object_or_404(User, user_id=request.session['user_id'])
    
    if request.method == 'POST':
        user.username = request.POST.get('username')
        user.nickname = request.POST.get('nickname')
        user.age = int(request.POST.get('age')) if request.POST.get('age') else None
        user.email = request.POST.get('email')
        user.phone = request.POST.get('phone')
        user.save()
        
        request.session['username'] = user.username
        messages.success(request, '资料更新成功')
        return redirect('user_profile')
    
    # 统计信息
    total_orders = Order.objects.filter(user=user).count()
    total_feedbacks = Feedback.objects.filter(user=user).count()
    
    context = {
        'user': user,
        'total_orders': total_orders,
        'total_feedbacks': total_feedbacks,
    }
    return render(request, 'core/profile.html', context)


def announcements_list(request):
    """公告列表"""
    announcement_type = request.GET.get('type', 'all')
    search = request.GET.get('search', '')
    
    announcements = Announcement.objects.filter(status='finalized')
    
    if announcement_type != 'all':
        announcements = announcements.filter(type=announcement_type)
    
    if search:
        announcements = announcements.filter(
            Q(title__icontains=search) | Q(content__icontains=search)
        )
    
    announcements = announcements.order_by('-created_at')
    
    paginator = Paginator(announcements, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'announcement_type': announcement_type,
        'search': search,
    }
    return render(request, 'core/announcements.html', context)


def announcement_detail(request, announcement_id):
    """公告详情"""
    announcement = get_object_or_404(Announcement, announcement_id=announcement_id, status='finalized')
    context = {'announcement': announcement}
    return render(request, 'core/announcement_detail.html', context)


def products_list(request):
    """商品列表"""
    search = request.GET.get('search', '')
    sort_by = request.GET.get('sort', 'name')
    
    products = Product.objects.all()
    
    if search:
        products = products.filter(
            Q(product_name__icontains=search) | 
            Q(description1__icontains=search) |
            Q(description2__icontains=search)
        )
    
    if sort_by == 'points_asc':
        products = products.order_by('points_required')
    elif sort_by == 'points_desc':
        products = products.order_by('-points_required')
    elif sort_by == 'date':
        products = products.order_by('-created_at')
    else:
        products = products.order_by('product_name')
    
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    user_points = 0
    if 'user_id' in request.session:
        try:
            user = User.objects.get(user_id=request.session['user_id'])
            user_points = user.points
        except User.DoesNotExist:
            pass
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'sort_by': sort_by,
        'user_points': user_points,
    }
    return render(request, 'core/products.html', context)


@community_access(api=True)
def create_order(request):
    """创建订单"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '请求方法错误'})
    
    if 'user_id' not in request.session:
        return JsonResponse({'success': False, 'message': '请先登录'})
    
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        
        user = User.objects.get(user_id=request.session['user_id'])
        product = Product.objects.get(product_id=product_id)
        
        # 检查库存
        if product.quantity <= 0:
            return JsonResponse({'success': False, 'message': '商品库存不足'})
        
        if user.points < product.points_required:
            return JsonResponse({'success': False, 'message': '积分不足'})
        
        order = Order.objects.create(
            product=product,
            user=user,
            payment_status='paid',
        )
        
        # 扣减用户积分和商品库存
        user.points -= product.points_required
        user.save()
        
        product.quantity -= 1
        product.save()
        
        return JsonResponse({'success': True, 'message': '兑换成功', 'order_id': order.order_id})
    
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


def my_orders(request):
    """我的订单"""
    if 'user_id' not in request.session:
        return redirect('login')
    
    user = User.objects.get(user_id=request.session['user_id'])
    orders = Order.objects.filter(user=user).order_by('-created_at')
    
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {'page_obj': page_obj, 'user': user}
    return render(request, 'core/my_orders.html', context)


def feedbacks_list(request):
    """意见反馈列表"""
    if 'user_id' not in request.session:
        return redirect('login')
    
    user = User.objects.get(user_id=request.session['user_id'])
    feedbacks = Feedback.objects.filter(user=user).order_by('-created_at')
    
    paginator = Paginator(feedbacks, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {'page_obj': page_obj}
    return render(request, 'core/feedbacks.html', context)


def create_feedback(request):
    """创建反馈"""
    if 'user_id' not in request.session:
        return redirect('login')
    
    if request.method == 'POST':
        user = User.objects.get(user_id=request.session['user_id'])
        content = request.POST.get('content')
        
        Feedback.objects.create(
            user=user,
            user_name=user.username,
            content=content
        )
        
        messages.success(request, '反馈提交成功')
        return redirect('feedbacks_list')
    
    return render(request, 'core/create_feedback.html')


def reports_list(request):
    """举报列表"""
    if 'user_id' not in request.session:
        return redirect('login')
    
    user_id = request.session['user_id']
    user = get_object_or_404(User, user_id=user_id)
    
    # 获取当前用户的举报记录
    reports = Report.objects.filter(reporter=user).order_by('-created_at')
    
    # 分页
    paginator = Paginator(reports, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'reports': page_obj,
        'page_obj': page_obj,
    }
    return render(request, 'core/reports.html', context)


def create_report(request):
    """创建举报"""
    if 'user_id' not in request.session:
        return redirect('login')
    
    if request.method == 'POST':
        user_id = request.session['user_id']
        user = get_object_or_404(User, user_id=user_id)
        
        report_type = request.POST.get('report_type', '').strip()
        reason = request.POST.get('reason', '').strip()
        video_file = request.FILES.get('video_file')
        
        # 验证必填字段
        if not reason or not report_type:
            messages.error(request, '举报类型和举报原因不能为空')
            return render(request, 'core/create_report.html')
        
        try:
            # 创建举报记录
            report = Report.objects.create(
                reporter=user,
                report_type=report_type,
                reason=reason
            )
            
            # 处理视频文件上传
            if video_file:
                from .utils import validate_video_file, save_uploaded_video
                
                # 验证视频文件
                is_valid, error_msg = validate_video_file(video_file)
                if not is_valid:
                    messages.error(request, f'视频文件验证失败: {error_msg}')
                    report.delete()  # 删除已创建的举报记录
                    return render(request, 'core/create_report.html')
                
                try:
                    # 保存视频文件
                    video_info = save_uploaded_video(video_file, 'report')
                    
                    # 创建视频记录
                    video_record = ReportVideo.objects.create(
                        report=report,
                        video_url=video_info['video_url']
                    )
                except Exception as e:
                    messages.error(request, f'视频保存失败: {str(e)}')
                    report.delete()  # 删除已创建的举报记录
                    return render(request, 'core/create_report.html')
            
            messages.success(request, '举报提交成功！我们会尽快处理您的举报。')
            return redirect('reports_list')
            
        except Exception as e:
            messages.error(request, f'提交失败：{str(e)}')
            return render(request, 'core/create_report.html')
    
    # GET请求，显示表单
    return render(request, 'core/create_report.html')


@community_access('admin', 'staff')
def abnormal_records_list(request):
    """异常记录列表（完善版）"""
    if 'user_id' not in request.session:
        return redirect('login')

    # 获取异常记录，按创建时间倒序
    abnormal_list = AbnormalRecord.objects.all().order_by('-created_at')

    def guess_location_from_url(url: str) -> str:
        """基于文件名或路径简单推测监控地点（不改数据库）"""
        if not url:
            return '未知地点'
        lower = url.lower()
        # 关键字到地点的简单映射（与监控页中的示例点对应）
        mapping = {
            'gate': '主入口',
            'door': '主入口',
            'front': '主入口',
            'parking': '地下停车场',
            'garage': '地下停车场',
            'garden': '中心花园',
            'playground': '中心花园',
            'gym': '户外健身区',
            'fitness': '户外健身区',
            'backdoor': '后门出入口',
            'rear': '后门出入口',
            'recycle': '生活区东侧',
            'trash': '生活区东侧',
        }
        for key, loc in mapping.items():
            if key in lower:
                return loc
        # 根据目录类型粗略分类
        if '/report/' in lower:
            return '监控区域（举报来源）'
        if '/abnormal/' in lower:
            return '监控区域（AI检测）'
        return '监控区域'

    def build_thumbnail_from_video_url(video_url: str) -> str:
        """根据视频URL推导缩略图URL；若不存在则优雅降级。兼容/static与/video两种访问路径"""
        if not video_url:
            return ''
        try:
            import os
            # 统一提取文件名
            basename = os.path.basename(video_url)
            thumb_rel = f"video/thumbnails/thumb_{os.path.splitext(basename)[0]}.jpg"
            thumb_url = f"/media/{thumb_rel}"
            if os.path.exists(os.path.join(settings.MEDIA_ROOT, thumb_rel)):
                return thumb_url
            # 在所有静态目录中检查缩略图是否已存在
            try:
                static_dirs = getattr(settings, 'STATICFILES_DIRS', [])
            except Exception:
                static_dirs = []
            for sd in static_dirs:
                thumb_full = os.path.join(sd, 'video', 'thumbnails', f"thumb_{os.path.splitext(basename)[0]}.jpg")
                if os.path.exists(thumb_full):
                    return thumb_url
            
            # 若不存在，尝试根据URL推导相对视频路径并生成缩略图
            if video_url.startswith('/media/'):
                video_rel = video_url.split('/media/', 1)[1]
            elif video_url.startswith('/static/'):
                # /static/video/abnormal/xxx.mp4 -> 相对路径 video/abnormal/xxx.mp4
                video_rel = video_url.split('/static/', 1)[1]
            elif video_url.startswith('/video/'):
                # /video/abnormal/xxx.mp4 -> 相对路径 video/abnormal/xxx.mp4
                video_rel = video_url.lstrip('/')
            else:
                # 其他情况，尽量规范化为相对路径
                video_rel = video_url.lstrip('/')
            
            try:
                from .utils import generate_video_thumbnail
                video_type = 'abnormal' if 'abnormal/' in video_rel else ('report' if 'report/' in video_rel else 'abnormal')
                gen_thumb = generate_video_thumbnail(video_rel, video_type)
                return gen_thumb or ''
            except Exception:
                return ''
        except Exception:
            return ''

    def url_to_rel_path(url: str) -> str:
        if not url:
            return ''
        if url.startswith('/media/'):
            return url.split('/media/', 1)[1]
        if url.startswith('/static/'):
            return url.split('/static/', 1)[1]
        if url.startswith('/video/'):
            return url.lstrip('/')
        return url.lstrip('/')

    def static_dirs_list():
        try:
            return list(getattr(settings, 'STATICFILES_DIRS', []))
        except Exception:
            return []

    def url_file_exists(url: str) -> bool:
        import os
        # 先尝试直接按文件系统路径判断（适配../../front/public/...或绝对路径等形式）
        try:
            norm = os.path.normpath(url)
            if os.path.isabs(norm) or norm.startswith('..') or norm.startswith('.'):
                abs_candidate = norm if os.path.isabs(norm) else os.path.normpath(os.path.join(settings.BASE_DIR, norm))
                if os.path.exists(abs_candidate):
                    return True
        except Exception:
            pass
        
        # 规范化成相对静态/媒体路径后再判断
        rel = url_to_rel_path(url)
        if not rel:
            return False
        try:
            if os.path.exists(os.path.join(settings.MEDIA_ROOT, rel.replace('/', os.sep))):
                return True
        except Exception:
            pass
        for sd in static_dirs_list():
            try:
                if os.path.exists(os.path.join(sd, rel.replace('/', os.sep))):
                    return True
            except Exception:
                pass
        return False

    # 组装供模板使用的数据结构（使用真实存在的文件）
    records = []
    for abnormal in abnormal_list:
        # 全量视频记录，按时间倒序
        videos_qs = AbnormalVideo.objects.filter(abnormal=abnormal).order_by('-created_at')
        # 过滤出本地真实存在的文件
        existing_urls = []
        for v in videos_qs:
            if v.video_url and url_file_exists(v.video_url):
                existing_urls.append(v.video_url)
        # 仅保留有真实视频的异常记录
        if not existing_urls:
            continue
        # 选择一个用于展示与缩略图
        video_url = existing_urls[0]
        records.append({
            'id': abnormal.abnormal_id,
            'type': abnormal.abnormal_type,
            'reason': abnormal.reason,
            'created_at': abnormal.created_at,
            'video_url': video_url,
            'video_count': len(existing_urls),
            'video_urls': existing_urls,
            'thumbnail_url': build_thumbnail_from_video_url(video_url),
            'location': guess_location_from_url(video_url),
            'source': 'AI检测' if '/abnormal/' in (video_url or '') else ('举报异常' if '/report/' in (video_url or '') else '异常记录'),
        })
    
    # 分页
    paginator = Paginator(records, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
    }
    return render(request, 'core/abnormal_records.html', context)


# 通知功能已移除，使用处理表替代


@community_access()
def monitoring(request):
    """每位登录用户只操作当前设备主动授权的摄像头。"""
    return render(request, 'core/camera_monitoring.html')

@community_access('admin', 'staff', api=True)
def api_latest_abnormal(request):
    """API: 获取最新一条异常记录（用于前端实时提醒）"""
    latest = AbnormalRecord.objects.order_by('-created_at').first()
    if not latest:
        return JsonResponse({'has_data': False})
    return JsonResponse({
        'has_data': True,
        'abnormal_id': latest.abnormal_id,
        'abnormal_type': latest.abnormal_type,
        'reason': latest.reason,
        'created_at': latest.created_at.isoformat(),
    })


@community_access('admin', 'staff', api=True)
def camera(request):
    return JsonResponse({
        'status': 'error',
        'message': '服务器视频分析由部署服务启动，请在服务器配置视频源。此网页不再启动服务器进程。',
    }, status=410)
