from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/monitoring/$', consumers.MonitoringConsumer.as_asgi()),
    re_path(r'ws/ai-alerts/$', consumers.AIAlertConsumer.as_asgi()),
]
