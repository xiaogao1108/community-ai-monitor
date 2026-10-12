"""
用户举报功能视图
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
import json
from .models import Report, ReportVideo, User
from .utils import save_uploaded_video, validate_video_file

def report_list(request):
    """举报信息列表 - 用户只能看到自己的举报"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    reports_list = Report.objects.filter(reporter=request.user).order_by('-created_at')
    
    # 搜索功能
    search_query = request.GET.get('search', '')
    if search_query:
        reports_list = reports_list.filter(
            Q(report_type__icontains=search_query) |
            Q(reason__icontains=search_query) |
            Q(reporter__username__icontains=search_query)
        )
    
    # 分页
    paginator = Paginator(reports_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'core/report_list.html', context)

def report_detail(request, report_id):
    """举报详情 - 用户只能查看自己的举报"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    report = get_object_or_404(Report, report_id=report_id, reporter=request.user)
    videos = ReportVideo.objects.filter(report=report)
    
    context = {
        'report': report,
        'videos': videos,
    }
    
    return render(request, 'core/report_detail.html', context)

def create_report(request):
    """创建举报"""
    if 'user_id' not in request.session:
        return redirect('login')
    
    if request.method == 'POST':
        try:
            # 获取表单数据
            report_type = request.POST.get('report_type')
            reason = request.POST.get('reason')
            video_file = request.FILES.get('video_file')
            
            # 验证数据
            if not report_type or not reason:
                messages.error(request, '请填写完整的举报信息')
                return redirect('create_report')
            
            # 获取当前用户
            user = User.objects.get(user_id=request.session['user_id'])
            
            # 创建举报记录
            report = Report.objects.create(
                reporter=user,
                report_type=report_type,
                reason=reason
            )
            
            # 处理视频文件
            if video_file:
                # 验证视频文件
                is_valid, error_msg = validate_video_file(video_file)
                if not is_valid:
                    messages.warning(request, f'视频文件: {error_msg}')
                else:
                    # 保存视频文件
                    video_info = save_uploaded_video(video_file, 'report')
                    
                    # 创建视频记录
                    ReportVideo.objects.create(
                        report=report,
                        video_url=video_info['video_url']
                    )
            
            # 举报提交成功，可以在这里添加其他处理逻辑
            
            messages.success(request, '举报提交成功！')
            return redirect('report_list')
            
        except Exception as e:
            messages.error(request, f'提交失败: {str(e)}')
            return redirect('create_report')
    
    return render(request, 'core/create_report.html')

@csrf_exempt
def api_create_report(request):
    """API: 创建举报（供AI系统调用）"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # 获取数据
            reporter_id = data.get('reporter_id', 100001)  # 默认用户ID
            report_type = data.get('report_type', 'AI自动举报')
            reason = data.get('reason', 'AI系统检测到可疑行为')
            video_url = data.get('video_url')
            
            # 创建举报记录
            report = Report.objects.create(
                reporter_id=reporter_id,
                report_type=report_type,
                reason=reason,
                created_at=timezone.now()
            )
            
            # 如果有视频，创建视频记录
            if video_url:
                ReportVideo.objects.create(
                    report=report,
                    video_url=video_url,
                    created_at=timezone.now()
                )
            
            return JsonResponse({
                'status': 'success',
                'report_id': report.report_id,
                'message': '举报信息已记录'
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

