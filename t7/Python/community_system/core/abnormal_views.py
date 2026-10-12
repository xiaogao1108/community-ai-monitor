"""
AI异常记录功能视图
"""

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
import json
from .models import AbnormalRecord, AbnormalVideo
from .utils import save_uploaded_video, validate_video_file
from .security import ai_ingest_required, community_access

@community_access('admin', 'staff')
def abnormal_list(request):
    """异常记录列表"""
    abnormal_list = AbnormalRecord.objects.all().order_by('-created_at')
    
    # 搜索功能
    search_query = request.GET.get('search', '')
    if search_query:
        abnormal_list = abnormal_list.filter(
            Q(abnormal_type__icontains=search_query) |
            Q(reason__icontains=search_query)
        )
    
    # 分页
    paginator = Paginator(abnormal_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'core/abnormal_list.html', context)

@community_access('admin', 'staff')
def abnormal_detail(request, abnormal_id):
    """异常记录详情"""
    abnormal = get_object_or_404(AbnormalRecord, abnormal_id=abnormal_id)
    videos = AbnormalVideo.objects.filter(abnormal=abnormal)
    
    context = {
        'abnormal': abnormal,
        'videos': videos,
    }
    
    return render(request, 'core/abnormal_detail.html', context)

@csrf_exempt
@ai_ingest_required
@transaction.atomic
def api_abnormal_detection(request):
    """API: 接收AI监控系统的异常检测结果"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # 获取数据
            abnormal_type = data.get('abnormal_type', 'AI检测异常')
            reason = data.get('reason', '系统自动检测到异常情况')
            if not isinstance(abnormal_type, str) or not isinstance(reason, str):
                return JsonResponse({'status': 'error', 'message': '异常类型和原因必须是文本'}, status=400)
            if len(abnormal_type) > 50:
                if abnormal_type not in reason:
                    reason = f'{abnormal_type}\n{reason}'
                abnormal_type = abnormal_type[:50]
            video_url = data.get('video_url')
            confidence = data.get('confidence', 0.85)
            location = data.get('location', '监控区域')
            
            # 创建异常记录
            abnormal = AbnormalRecord.objects.create(
                abnormal_type=abnormal_type,
                reason=reason,
                created_at=timezone.now()
            )
            
            # 如果有视频，创建视频记录
            if video_url:
                # 规范化视频URL到/static/video/abnormal/<文件名>
                try:
                    import os
                    # 提取文件名
                    basename = os.path.basename(video_url)
                    # 如果是/video/abnormal/前缀，统一改为/static
                    if video_url.startswith('/video/abnormal/'):
                        video_url = f"/static/video/abnormal/{basename}"
                    # 如果是文件系统路径或其他形式，提取文件名后拼装为/static/video/abnormal/
                    elif not video_url.startswith('/static/'):
                        video_url = f"/static/video/abnormal/{basename}"
                except Exception:
                    # 避免异常影响入库
                    pass
                
                AbnormalVideo.objects.create(
                    abnormal=abnormal,
                    video_url=video_url,
                    created_at=timezone.now()
                )
                
                # 记录日志
                print(f"异常记录已创建: ID={abnormal.abnormal_id}, 视频={video_url}")
            
            return JsonResponse({
                'status': 'success',
                'abnormal_id': abnormal.abnormal_id,
                'message': '异常记录已创建',
                'video_url': video_url
            })
            
        except Exception as e:
            transaction.set_rollback(True)
            print(f"异常检测API错误: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

@csrf_exempt
@ai_ingest_required
def api_abnormal_video_upload(request):
    """API: 上传AI异常视频"""
    if request.method == 'POST':
        try:
            # 获取上传的视频文件
            video_file = request.FILES.get('video')
            abnormal_id = request.POST.get('abnormal_id')
            
            if not video_file or not abnormal_id:
                return JsonResponse({
                    'status': 'error',
                    'message': '缺少必要参数'
                }, status=400)
            
            is_valid, error_msg = validate_video_file(video_file)
            if not is_valid:
                return JsonResponse({'status': 'error', 'message': error_msg}, status=400)

            # 获取异常记录
            abnormal = get_object_or_404(AbnormalRecord, abnormal_id=abnormal_id)
            
            # 保存视频文件
            video_info = save_uploaded_video(video_file, 'abnormal')
            
            # 创建视频记录
            video = AbnormalVideo.objects.create(
                abnormal=abnormal,
                video_url=video_info['video_url'],
                created_at=timezone.now()
            )
            
            return JsonResponse({
                'status': 'success',
                'video_id': video.abnormal_video_id,
                'video_url': video_info['video_url'],
                'message': '视频上传成功'
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

@community_access('admin', 'staff', api=True)
def process_abnormal(request, abnormal_id):
    """处理异常记录"""
    if request.method == 'POST':
        try:
            abnormal = get_object_or_404(AbnormalRecord, abnormal_id=abnormal_id)
            action = request.POST.get('action')
            
            if action == 'confirm':
                # 确认异常
                # 这里可以添加处理逻辑
                pass
            elif action == 'resolve':
                # 解决异常
                # 这里可以添加处理逻辑
                pass
            elif action == 'false_alarm':
                # 标记为误报
                # 这里可以添加处理逻辑
                pass
            
            return JsonResponse({
                'status': 'success',
                'message': '处理完成'
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
