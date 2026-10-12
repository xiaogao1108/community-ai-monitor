from django.contrib import admin
from django.contrib.auth.hashers import identify_hasher, make_password
from django.utils import timezone
from .models import (
    User, Feedback, Product, Order, Report, ReportVideo,
    AbnormalRecord, AbnormalVideo, Announcement, FeedbackProcessing,
    ReportProcessing, AbnormalProcessing
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'username', 'account', 'nickname', 'type', 'points', 'created_at')
    list_filter = ('type', 'created_at')
    search_fields = ('username', 'account', 'nickname', 'email')
    readonly_fields = ('user_id', 'created_at', 'updated_at')
    list_per_page = 20

    def save_model(self, request, obj, form, change):
        try:
            identify_hasher(obj.password)
        except ValueError:
            obj.password = make_password(obj.password)
        super().save_model(request, obj, form, change)
    
    fieldsets = (
        ('基本信息', {
            'fields': ('username', 'account', 'password', 'nickname', 'age')
        }),
        ('联系方式', {
            'fields': ('email', 'phone')
        }),
        ('系统信息', {
            'fields': ('type', 'points', 'created_at', 'updated_at')
        }),
    )


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('feedback_id', 'user_name', 'content_preview', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user_name', 'content')
    readonly_fields = ('feedback_id', 'created_at', 'user_name')
    list_per_page = 20
    actions = []
    
    fieldsets = (
        ('反馈信息', {
            'fields': ('feedback_id', 'user', 'user_name', 'content', 'created_at')
        }),
        ('处理信息', {
            'fields': ('status',)
        }),
    )
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = '反馈内容'
    



@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_id', 'product_name', 'points_required', 'has_image', 'created_at')
    list_filter = ('points_required', 'created_at')
    search_fields = ('product_name', 'description1', 'description2')
    readonly_fields = ('product_id', 'created_at')
    list_per_page = 20
    
    fieldsets = (
        ('基本信息', {
            'fields': ('product_name', 'points_required')
        }),
        ('商品描述', {
            'fields': ('description1', 'description2')
        }),
        ('商品图片', {
            'fields': ('image_url',)
        }),
        ('系统信息', {
            'fields': ('product_id', 'created_at')
        }),
    )
    
    def has_image(self, obj):
        return bool(obj.image_url)
    has_image.boolean = True
    has_image.short_description = '有图片'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'user', 'product', 'payment_status', 'created_at', 'payment_time')
    list_filter = ('payment_status', 'created_at')
    search_fields = ('user__username', 'product__product_name')
    readonly_fields = ('order_id', 'created_at')
    list_per_page = 20


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('report_id', 'reporter', 'report_type', 'reason_preview', 'created_at')
    list_filter = ('report_type', 'created_at')
    search_fields = ('reporter__username', 'report_type', 'reason')
    readonly_fields = ('report_id', 'created_at')
    list_per_page = 20
    
    def reason_preview(self, obj):
        return obj.reason[:30] + '...' if len(obj.reason) > 30 else obj.reason
    reason_preview.short_description = '举报原因'


@admin.register(ReportVideo)
class ReportVideoAdmin(admin.ModelAdmin):
    list_display = ('report_video_id', 'report', 'video_url', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('report__report_type', 'video_url')
    readonly_fields = ('report_video_id', 'created_at')
    list_per_page = 20


@admin.register(AbnormalRecord)
class AbnormalRecordAdmin(admin.ModelAdmin):
    list_display = ('abnormal_id', 'abnormal_type', 'reason_preview', 'created_at')
    list_filter = ('abnormal_type', 'created_at')
    search_fields = ('abnormal_type', 'reason')
    readonly_fields = ('abnormal_id', 'created_at')
    list_per_page = 20
    
    def reason_preview(self, obj):
        return obj.reason[:30] + '...' if len(obj.reason) > 30 else obj.reason
    reason_preview.short_description = '异常原因'


@admin.register(AbnormalVideo)
class AbnormalVideoAdmin(admin.ModelAdmin):
    list_display = ('abnormal_video_id', 'abnormal', 'video_url', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('abnormal__abnormal_type', 'video_url')
    readonly_fields = ('abnormal_video_id', 'created_at')
    list_per_page = 20


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('announcement_id', 'title', 'type', 'status', 'created_at', 'updated_at')
    list_filter = ('type', 'status', 'created_at')
    search_fields = ('title', 'content')
    readonly_fields = ('announcement_id', 'created_at', 'updated_at')
    list_per_page = 20
    
    fieldsets = (
        ('基本信息', {
            'fields': ('title', 'content', 'type', 'status')
        }),
        ('媒体', {
            'fields': ('image_url',)
        }),
        ('系统信息', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(FeedbackProcessing)
class FeedbackProcessingAdmin(admin.ModelAdmin):
    list_display = ('processing_id', 'feedback', 'processing_result', 'created_at', 'processed_at')
    list_filter = ('created_at', 'processed_at')
    search_fields = ('feedback__content', 'processing_result')
    readonly_fields = ('processing_id', 'created_at')
    list_per_page = 20


@admin.register(ReportProcessing)
class ReportProcessingAdmin(admin.ModelAdmin):
    list_display = ('processing_id', 'report', 'status', 'created_at', 'processed_at')
    list_filter = ('status', 'created_at')
    search_fields = ('report__reason', 'processing_result')
    readonly_fields = ('processing_id', 'created_at')
    list_per_page = 20


@admin.register(AbnormalProcessing)
class AbnormalProcessingAdmin(admin.ModelAdmin):
    list_display = ('processing_id', 'abnormal', 'status', 'created_at', 'processed_at')
    list_filter = ('status', 'created_at')
    search_fields = ('abnormal__reason', 'processing_description')
    readonly_fields = ('processing_id', 'created_at')
    list_per_page = 20
