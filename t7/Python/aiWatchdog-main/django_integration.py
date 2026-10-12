"""
AI监控系统与Django系统的集成模块
负责将AI检测结果发送到Django系统
"""

import httpx
import json
import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, Any
from config import read_secret

# Django系统配置
DJANGO_BASE_URL = os.environ.get("DJANGO_BASE_URL", "http://127.0.0.1:8000").rstrip('/')
DJANGO_API_ENDPOINTS = {
    'abnormal': '/api/ai/abnormal/',
    'report': '/api/ai/report/',
    'status': '/api/ai/status/'
}

class DjangoIntegration:
    def __init__(self):
        headers = {'X-Forwarded-Proto': 'https'}
        token = read_secret('AI_INGEST_TOKEN')
        if token:
            headers['Authorization'] = 'Bearer ' + token
        self.client = httpx.AsyncClient(timeout=10.0, headers=headers)
        self.logger = logging.getLogger(__name__)
    
    async def send_abnormal_detection(self, abnormal_data: Dict[str, Any]) -> bool:
        """
        发送异常检测结果到Django系统
        
        Args:
            abnormal_data: 异常数据字典
            
        Returns:
            bool: 发送是否成功
        """
        try:
            url = f"{DJANGO_BASE_URL}{DJANGO_API_ENDPOINTS['abnormal']}"
            
            # 构造发送数据
            data = {
                'abnormal_type': abnormal_data.get('abnormal_type', 'AI检测异常'),
                'reason': abnormal_data.get('reason', '系统自动检测到异常情况'),
                'video_url': abnormal_data.get('video_url'),
                'timestamp': datetime.now().isoformat(),
                'confidence': abnormal_data.get('confidence', 0.85),
                'location': abnormal_data.get('location', '未知位置')
            }
            
            response = await self.client.post(url, json=data)
            
            if response.status_code == 200:
                result = response.json()
                self.logger.info(f"异常数据已发送到Django系统: {result}")
                return True
            else:
                self.logger.error(f"发送异常数据失败，HTTP 状态码: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"发送异常数据异常: {type(e).__name__}")
            return False
    
    async def send_report_submission(self, report_data: Dict[str, Any]) -> bool:
        """
        发送举报信息到Django系统
        
        Args:
            report_data: 举报数据字典
            
        Returns:
            bool: 发送是否成功
        """
        try:
            url = f"{DJANGO_BASE_URL}{DJANGO_API_ENDPOINTS['report']}"
            
            # 构造发送数据
            data = {
                'report_type': report_data.get('report_type', 'AI自动举报'),
                'reason': report_data.get('reason', 'AI系统检测到可疑行为'),
                'video_url': report_data.get('video_url'),
                'reporter_id': report_data.get('reporter_id', 100001),  # 默认用户ID
                'timestamp': datetime.now().isoformat(),
                'location': report_data.get('location', '未知位置'),
                'severity': report_data.get('severity', 'medium')
            }
            
            response = await self.client.post(url, json=data)
            
            if response.status_code == 200:
                result = response.json()
                self.logger.info(f"举报数据已发送到Django系统: {result}")
                return True
            else:
                self.logger.error(f"发送举报数据失败，HTTP 状态码: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"发送举报数据异常: {type(e).__name__}")
            return False
    
    async def check_django_status(self) -> bool:
        """
        检查Django系统状态
        
        Returns:
            bool: Django系统是否在线
        """
        try:
            url = f"{DJANGO_BASE_URL}{DJANGO_API_ENDPOINTS['status']}"
            response = await self.client.get(url)
            
            if response.status_code == 200:
                result = response.json()
                self.logger.info(f"Django系统状态: {result}")
                return True
            else:
                self.logger.warning(f"Django系统状态检查失败: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.warning(f"Django系统状态检查异常: {type(e).__name__}")
            return False
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()

# 全局集成实例
django_integration = DjangoIntegration()

# 便捷函数
async def send_abnormal_to_django(abnormal_type: str, reason: str, video_url: str = None, **kwargs):
    """发送异常检测结果到Django系统"""
    data = {
        'abnormal_type': abnormal_type,
        'reason': reason,
        'video_url': video_url,
        'confidence': kwargs.get('confidence', 0.85),
        'location': kwargs.get('location', '监控区域')
    }
    return await django_integration.send_abnormal_detection(data)

async def send_report_to_django(report_type: str, reason: str, video_url: str = None, **kwargs):
    """发送举报信息到Django系统"""
    data = {
        'report_type': report_type,
        'reason': reason,
        'video_url': video_url,
        'reporter_id': kwargs.get('reporter_id', 100001)
    }
    return await django_integration.send_report_submission(data)

async def check_django_connection():
    """检查Django系统连接"""
    return await django_integration.check_django_status()
