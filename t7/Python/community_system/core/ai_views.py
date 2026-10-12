from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
import json
from .models import AbnormalRecord, AbnormalVideo, Report, ReportVideo
# WebSocket功能暂时禁用
# from channels.layers import get_channel_layer
# from asgiref.sync import async_to_sync

# channel_layer = get_channel_layer()

@csrf_exempt
def ai_abnormal_detection(request):
    """接收AI监控系统的异常检测结果"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # 创建异常记录
            abnormal_record = AbnormalRecord.objects.create(
                abnormal_type=data.get('abnormal_type', 'AI检测异常'),
                reason=data.get('reason', '系统自动检测到异常情况'),
                created_at=timezone.now()
            )
            
            # 如果有视频，创建视频记录
            if data.get('video_url'):
                AbnormalVideo.objects.create(
                    abnormal=abnormal_record,
                    video_url=data.get('video_url'),
                    created_at=timezone.now()
                )
            
            # WebSocket广播功能暂时禁用
            # async_to_sync(channel_layer.group_send)(
            #     'ai_alerts',
            #     {
            #         'type': 'ai_alert_broadcast',
            #         'data': {
            #             'abnormal_id': abnormal_record.abnormal_id,
            #             'abnormal_type': abnormal_record.abnormal_type,
            #             'reason': abnormal_record.reason,
            #             'timestamp': abnormal_record.created_at.isoformat(),
            #             'video_url': data.get('video_url')
            #         }
            #     }
            # )
            
            return JsonResponse({
                'status': 'success', 
                'abnormal_id': abnormal_record.abnormal_id,
                'message': '异常记录已创建并广播'
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

@csrf_exempt
def ai_report_submission(request):
    """接收AI监控系统的举报信息"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # 创建举报记录
            report = Report.objects.create(
                reporter_id=data.get('reporter_id', 100001),  # 默认用户ID
                report_type=data.get('report_type', 'AI自动举报'),
                reason=data.get('reason', 'AI系统检测到可疑行为'),
                created_at=timezone.now()
            )
            
            # 如果有视频，创建视频记录
            if data.get('video_url'):
                ReportVideo.objects.create(
                    report=report,
                    video_url=data.get('video_url'),
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

@csrf_exempt
def ai_system_status(request):
    """AI监控系统状态检查"""
    if request.method == 'GET':
        return JsonResponse({
            'status': 'online',
            'timestamp': timezone.now().isoformat(),
            'django_system': 'connected'
        })
    
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

def monitoring_dashboard(request):
    """AI监控仪表板 - 连接到真正的AI监控系统"""
    try:
        # 检查AI系统连接状态
        ai_status = check_ai_system_status()
        
        # 获取最近的异常记录
        recent_abnormal = AbnormalRecord.objects.all().order_by('-created_at')[:10]
        
        # 获取监控统计
        total_abnormal = AbnormalRecord.objects.count()
        today_abnormal = AbnormalRecord.objects.filter(
            created_at__date=timezone.now().date()
        ).count()
        
        context = {
            'ai_status': ai_status,
            'recent_abnormal': recent_abnormal,
            'total_abnormal': total_abnormal,
            'today_abnormal': today_abnormal,
            'ai_system_url': 'http://127.0.0.1:8001',  # AI系统地址
        }
        
        return render(request, 'core/monitoring_dashboard.html', context)
        
    except Exception as e:
        context = {
            'ai_status': {'status': 'error', 'message': str(e)},
            'recent_abnormal': [],
            'total_abnormal': 0,
            'today_abnormal': 0,
            'ai_system_url': 'http://127.0.0.1:8001',
        }
        return render(request, 'core/monitoring_dashboard.html', context)

def check_ai_system_status():
    """检查AI系统状态"""
    try:
        import requests
        response = requests.get('http://127.0.0.1:8001/status', timeout=3)
        if response.status_code == 200:
            data = response.json()
            return {
                'status': 'online', 
                'message': 'AI监控系统正常运行',
                'details': data
            }
        else:
            return {'status': 'error', 'message': f'AI系统响应异常: {response.status_code}'}
    except requests.exceptions.ConnectionError:
        return {'status': 'offline', 'message': 'AI监控系统未启动'}
    except Exception as e:
        return {'status': 'error', 'message': f'连接错误: {str(e)}'}

def camera_test(request):
    """摄像头稳定性测试页面"""
    return render(request, 'core/camera_test.html')

def abnormal_records_list(request):
    """异常记录列表"""
    abnormal_list = AbnormalRecord.objects.all().order_by('-created_at')
    
    # 分页
    paginator = Paginator(abnormal_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    
    return render(request, 'core/abnormal_records.html', context)

def reports_list(request):
    """举报信息列表"""
    reports_list = Report.objects.all().order_by('-created_at')
    
    # 分页
    paginator = Paginator(reports_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    
    return render(request, 'core/reports.html', context)
