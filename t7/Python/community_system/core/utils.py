"""
工具函数模块
包含文件上传、视频处理等功能
"""

import os
import uuid
import cv2
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from PIL import Image
import tempfile

def generate_unique_filename(original_filename):
    """生成唯一文件名"""
    ext = os.path.splitext(original_filename)[1]
    unique_id = str(uuid.uuid4())
    return f"{unique_id}{ext}"

def save_uploaded_video(video_file, video_type='report'):
    """
    保存上传的视频文件
    
    Args:
        video_file: 上传的视频文件
        video_type: 视频类型 ('report' 或 'abnormal')
    
    Returns:
        dict: 包含文件路径、URL等信息
    """
    # 生成唯一文件名
    filename = generate_unique_filename(video_file.name)
    
    # 确定存储路径
    if video_type == 'report':
        storage_path = f"video/report/{filename}"
    elif video_type == 'abnormal':
        storage_path = f"video/abnormal/{filename}"
    else:
        raise ValueError("video_type must be 'report' or 'abnormal'")
    
    # 保存文件
    file_path = default_storage.save(storage_path, video_file)
    
    # 生成访问URL
    video_url = f"/video/{video_type}/{filename}"
    
    # 获取文件信息
    file_size = video_file.size
    
    # 生成缩略图
    thumbnail_path = generate_video_thumbnail(file_path, video_type)
    
    return {
        'file_path': file_path,
        'video_url': video_url,
        'file_size': file_size,
        'thumbnail_path': thumbnail_path,
        'filename': filename
    }

def generate_video_thumbnail(video_path, video_type='report'):
    """
    生成视频缩略图
    
    Args:
        video_path: 视频文件路径
        video_type: 视频类型
    
    Returns:
        str: 缩略图URL
    """
    try:
        # 构建完整视频路径
        full_video_path = os.path.join(settings.MEDIA_ROOT, video_path)
        if not os.path.exists(full_video_path):
            full_video_path = os.path.join(settings.STATICFILES_DIRS[0], video_path)
        
        # 使用OpenCV读取视频
        cap = cv2.VideoCapture(full_video_path)
        
        if not cap.isOpened():
            return None
        
        # 获取视频信息
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        
        # 读取第一帧作为缩略图
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            return None
        
        # 生成缩略图文件名
        video_filename = os.path.basename(video_path)
        thumbnail_filename = f"thumb_{os.path.splitext(video_filename)[0]}.jpg"
        thumbnail_path = f"video/thumbnails/{thumbnail_filename}"
        
        # 调整缩略图大小
        height, width = frame.shape[:2]
        if width > 300:
            ratio = 300 / width
            new_width = 300
            new_height = int(height * ratio)
            frame = cv2.resize(frame, (new_width, new_height))
        
        # 保存缩略图
        thumbnail_full_path = os.path.join(settings.MEDIA_ROOT, thumbnail_path)
        os.makedirs(os.path.dirname(thumbnail_full_path), exist_ok=True)
        
        cv2.imwrite(thumbnail_full_path, frame)
        
        return f"/media/{thumbnail_path}"
        
    except Exception as e:
        print(f"生成缩略图失败: {e}")
        return None

def get_video_info(video_path):
    """
    获取视频信息
    
    Args:
        video_path: 视频文件路径
    
    Returns:
        dict: 视频信息
    """
    try:
        full_video_path = os.path.join(settings.MEDIA_ROOT, video_path)
        if not os.path.exists(full_video_path):
            full_video_path = os.path.join(settings.STATICFILES_DIRS[0], video_path)
        
        cap = cv2.VideoCapture(full_video_path)
        
        if not cap.isOpened():
            return None
        
        # 获取视频信息
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = frame_count / fps if fps > 0 else 0
        
        cap.release()
        
        return {
            'fps': fps,
            'frame_count': frame_count,
            'width': width,
            'height': height,
            'duration': duration
        }
        
    except Exception as e:
        print(f"获取视频信息失败: {e}")
        return None

def validate_video_file(video_file):
    """
    验证视频文件
    
    Args:
        video_file: 上传的视频文件
    
    Returns:
        tuple: (is_valid, error_message)
    """
    # 检查文件大小 (限制为100MB)
    max_size = 100 * 1024 * 1024  # 100MB
    if video_file.size > max_size:
        return False, "视频文件大小不能超过100MB"
    
    # 检查文件类型
    allowed_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv']
    file_ext = os.path.splitext(video_file.name)[1].lower()
    if file_ext not in allowed_extensions:
        return False, f"不支持的视频格式。支持的格式: {', '.join(allowed_extensions)}"
    
    return True, None
