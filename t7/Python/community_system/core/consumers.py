import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import AbnormalRecord, Report
from django.utils import timezone

class MonitoringConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = 'monitoring'
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'monitoring_status':
            # 广播监控状态更新
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'monitoring_update',
                    'data': data
                }
            )

    async def monitoring_update(self, event):
        # 发送监控更新到WebSocket
        await self.send(text_data=json.dumps({
            'type': 'monitoring_update',
            'data': event['data']
        }))

class AIAlertConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = 'ai_alerts'
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'ai_alert':
            # 处理AI警报
            await self.handle_ai_alert(data)

    async def handle_ai_alert(self, data):
        # 保存异常记录到数据库
        abnormal_record = await self.save_abnormal_record(data)
        
        # 广播警报
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'ai_alert_broadcast',
                'data': {
                    'abnormal_id': abnormal_record.abnormal_id,
                    'abnormal_type': abnormal_record.abnormal_type,
                    'reason': abnormal_record.reason,
                    'timestamp': abnormal_record.created_at.isoformat()
                }
            }
        )

    @database_sync_to_async
    def save_abnormal_record(self, data):
        return AbnormalRecord.objects.create(
            abnormal_type=data.get('abnormal_type', 'AI检测异常'),
            reason=data.get('reason', '系统自动检测到异常情况'),
            created_at=timezone.now()
        )

    # 通知功能已移除

    async def ai_alert_broadcast(self, event):
        # 发送AI警报到WebSocket
        await self.send(text_data=json.dumps({
            'type': 'ai_alert',
            'data': event['data']
        }))
