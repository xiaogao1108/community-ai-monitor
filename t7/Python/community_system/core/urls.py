from django.urls import path
from . import views
from . import product_api_views
from . import file_upload_views
from . import abnormal_views
from . import media_views
from . import camera_views

urlpatterns = [
    path('media/<path:path>', media_views.protected_media, name='protected_media'),
    path('video/<path:path>', media_views.protected_video, name='protected_video'),
    path('static/video/<path:path>', media_views.protected_video),
    # 基本页面
    path('', views.home, name='home'),
    
    # 用户认证
    path('login/', views.user_login, name='login'),
    path('register/', views.user_register, name='register'),
    path('logout/', views.user_logout, name='logout'),
    path('profile/', views.user_profile, name='user_profile'),
    
    # 公告模块
    path('announcements/', views.announcements_list, name='announcements_list'),
    path('announcements/<int:announcement_id>/', views.announcement_detail, name='announcement_detail'),
    
    # 商品和订单模块
    path('products/', views.products_list, name='products_list'),
    path('api/create-order/', views.create_order, name='create_order'),
    path('my-orders/', views.my_orders, name='my_orders'),
    
    # 商品REST API接口
    path('api/products/select/', product_api_views.api_products_select, name='api_products_select'),
    path('api/products/add/', product_api_views.api_products_add, name='api_products_add'),
    path('api/products/update/', product_api_views.api_products_update, name='api_products_update'),
    path('api/products/delete/id/<int:product_id>/', product_api_views.api_products_delete, name='api_products_delete'),
    path('api/products/select/id/<int:product_id>/', product_api_views.api_products_select_by_id, name='api_products_select_by_id'),
    
    # 文件上传API
    path('api/files/upload/', file_upload_views.api_files_upload, name='api_files_upload'),
    path('api/announcements/files/upload/', file_upload_views.api_announcement_files_upload, name='api_announcement_files_upload'),
    
    # 反馈模块
    path('feedbacks/', views.feedbacks_list, name='feedbacks_list'),
    path('feedbacks/create/', views.create_feedback, name='create_feedback'),
    
    # 举报模块
    path('reports/', views.reports_list, name='reports_list'),
    path('reports/create/', views.create_report, name='create_report'),
    
    # 异常记录
    path('abnormal-records/', views.abnormal_records_list, name='abnormal_records_list'),
    path('abnormal-records/<int:abnormal_id>/', abnormal_views.abnormal_detail, name='abnormal_detail'),

    # AI异常API
    path('api/ai/abnormal/', abnormal_views.api_abnormal_detection, name='api_abnormal_detection'),
    path('api/ai/abnormal/video/upload/', abnormal_views.api_abnormal_video_upload, name='api_abnormal_video_upload'),
    
    # 监控系统
    path('monitoring/', views.monitoring, name='monitoring'),
    path('api/cameras/start/', camera_views.start, name='camera_start'),
    path('api/cameras/<uuid:camera_id>/frames/', camera_views.frames),
    path('api/cameras/<uuid:camera_id>/status/', camera_views.status),
    path('api/cameras/<uuid:camera_id>/stop/', camera_views.stop),
    path('camera/', views.camera, name='camera')
    
    # 实时预警API
    ,path('api/alerts/latest/', views.api_latest_abnormal, name='api_latest_abnormal')
    # 通知系统已移除
]
