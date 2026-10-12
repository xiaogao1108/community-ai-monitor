"""
文件上传API视图
处理图片和文件上传功能
"""

import os
import uuid
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from PIL import Image, UnidentifiedImageError
from .security import community_access

def generate_unique_filename(original_filename):
    """生成唯一文件名"""
    ext = os.path.splitext(original_filename)[1]
    unique_id = str(uuid.uuid4())
    return f"{unique_id}{ext}"

def validate_image_file(image_file):
    """
    验证图片文件
    
    Args:
        image_file: 上传的图片文件
    
    Returns:
        tuple: (is_valid, error_message)
    """
    # 检查文件大小 (限制为5MB)
    max_size = 5 * 1024 * 1024  # 5MB
    if image_file.size > max_size:
        return False, "图片文件大小不能超过5MB"
    
    # 检查文件类型
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    file_ext = os.path.splitext(image_file.name)[1].lower()
    if file_ext not in allowed_extensions:
        return False, f"不支持的图片格式。支持的格式: {', '.join(allowed_extensions)}"
    
    try:
        with Image.open(image_file) as image:
            image.verify()
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
        return False, '文件不是有效图片'
    finally:
        image_file.seek(0)
    return True, None

@community_access(api=True)
@require_http_methods(["POST"])
def api_files_upload(request):
    """
    通用文件上传API
    
    POST参数:
        file: 上传的文件
        type: 图片类型 ('product', 'announcement', 'profile')
    
    返回:
        {
            "state": 状态码,
            "msg": 消息,
            "data": {
                "file_url": 文件访问URL,
                "file_name": 文件名,
                "file_size": 文件大小
            }
        }
    """
    try:
        # 检查是否有文件上传
        if 'file' not in request.FILES:
            return JsonResponse({
                'state': 4001,
                'msg': '未找到上传的文件',
                'data': None
            })
        
        uploaded_file = request.FILES['file']
        default_type = 'announcement' if request.resolver_match.url_name == 'api_announcement_files_upload' else 'general'
        file_type = request.POST.get('type', default_type)
        if file_type in ('product', 'announcement') and request.community_user.type != 'admin':
            return JsonResponse({'msg': '没有上传权限'}, status=403)
        
        # 根据文件类型设置存储路径和验证规则
        if file_type == 'product':
            # 商品图片
            is_valid, error_msg = validate_image_file(uploaded_file)
            if not is_valid:
                return JsonResponse({
                    'state': 4002,
                    'msg': error_msg,
                    'data': None
                })
            storage_subpath = "imgs/products/"
            
        elif file_type == 'announcement':
            # 公告图片
            is_valid, error_msg = validate_image_file(uploaded_file)
            if not is_valid:
                return JsonResponse({
                    'state': 4002,
                    'msg': error_msg,
                    'data': None
                })
            storage_subpath = "imgs/announcements/"
            
        elif file_type == 'profile':
            # 用户头像
            is_valid, error_msg = validate_image_file(uploaded_file)
            if not is_valid:
                return JsonResponse({
                    'state': 4002,
                    'msg': error_msg,
                    'data': None
                })
            storage_subpath = "imgs/profiles/"
            
        else:
            return JsonResponse({'msg': '只允许商品、公告或头像图片上传'}, status=400)
        
        # 生成唯一文件名
        filename = generate_unique_filename(uploaded_file.name)
        storage_path = f"{storage_subpath}{filename}"
        
        # 保存文件
        file_path = default_storage.save(storage_path, ContentFile(uploaded_file.read()))
        
        # 生成访问URL
        file_url = f"/static/{storage_path}"
        
        # 获取文件信息
        file_size = uploaded_file.size
        
        print(f"文件上传成功: {file_url}")
        
        return JsonResponse({
            'state': 2001,
            'msg': '文件上传成功',
            'data': {
                'file_url': file_url,
                'file_name': filename,
                'file_size': file_size
            }
        })
        
    except Exception as e:
        print(f"文件上传失败: {e}")
        return JsonResponse({
            'state': 5001,
            'msg': f'文件上传失败: {str(e)}',
            'data': None
        })

@community_access('admin', api=True)
@require_http_methods(["POST"])
def api_announcement_files_upload(request):
    """
    公告文件上传API（兼容现有前端）
    
    这个函数专门处理公告文件上传，保持与现有前端代码的兼容性
    """
    return api_files_upload(request)
