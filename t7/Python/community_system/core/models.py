# core/models.py
import uuid

from django.db import models
from django.core.validators import MinLengthValidator


class User(models.Model):
    """用户表"""
    TYPE_CHOICES = [
        ('resident', '住户'),
        ('admin', '管理员'),
        ('staff', '值班员工'),
    ]

    user_id = models.AutoField(primary_key=True, verbose_name='用户ID')
    username = models.CharField(max_length=50, null=False, verbose_name='用户姓名')
    account = models.CharField(
        max_length=30,
        unique=True,
        null=False,
        validators=[MinLengthValidator(6)],
        verbose_name='账号(6位以上)',
        db_column='ACCOUNT'
    )
    password = models.CharField(
        max_length=128,
        null=False,
        validators=[MinLengthValidator(6)],
        verbose_name='密码(6位以上)',
        db_column='PASSWORD'
    )
    nickname = models.CharField(max_length=50, null=True, blank=True, verbose_name='昵称')
    age = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='年龄')
    points = models.IntegerField(default=0, verbose_name='积分')
    email = models.EmailField(max_length=100, null=True, blank=True, verbose_name='邮箱')
    phone = models.CharField(max_length=20, null=True, blank=True, verbose_name='电话号码')
    address = models.CharField(max_length=255, null=True, blank=True, verbose_name='用户地址')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, null=False, verbose_name='类型', db_column='TYPE')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'users'
        verbose_name = '用户'
        verbose_name_plural = '用户'
        indexes = [
            models.Index(fields=['account'], name='idx_users_account'),
            models.Index(fields=['type'], name='idx_users_type'),
        ]

    def __str__(self):
        return f"{self.username}({self.account})"


class Feedback(models.Model):
    """意见反馈表"""
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('processed', '已处理')
    ]

    feedback_id = models.AutoField(primary_key=True, verbose_name='反馈ID')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    user_name = models.CharField(max_length=50, null=False, verbose_name='反馈时用户姓名')
    content = models.TextField(null=False, verbose_name='反馈内容')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='反馈时间')
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='处理状态',
        db_column='STATUS'
    )

    class Meta:
        db_table = 'feedbacks'
        verbose_name = '意见反馈'
        verbose_name_plural = '意见反馈'
        indexes = [
            models.Index(fields=['status'], name='idx_feedbacks_status'),
            models.Index(fields=['created_at'], name='idx_feedbacks_created'),
        ]

    def __str__(self):
        return f"{self.user_name} - {self.content[:20]}..."


class FeedbackProcessing(models.Model):
    """意见反馈处理表"""
    processing_id = models.AutoField(primary_key=True, verbose_name='反馈处理ID')
    feedback = models.ForeignKey(Feedback, on_delete=models.CASCADE, verbose_name='关联的意见反馈ID')
    processing_result = models.CharField(max_length=1500, default='', verbose_name='处理结果描述(1500字以内)')
    created_at = models.DateTimeField(verbose_name='创建时间(与对应反馈时间相同)')
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name='处理时间')

    class Meta:
        db_table = 'feedback_processing'
        verbose_name = '意见反馈处理'
        verbose_name_plural = '意见反馈处理'
        indexes = [
            models.Index(fields=['feedback'], name='idx_feedback_proc_fid'),
            models.Index(fields=['created_at'], name='idx_feedback_proc_created'),
        ]

    def __str__(self):
        return f"反馈处理 - {self.feedback.user_name}"


class Product(models.Model):
    """商品表"""
    product_id = models.AutoField(primary_key=True, verbose_name='商品ID')
    product_name = models.CharField(max_length=100, null=False, verbose_name='商品名')
    points_required = models.IntegerField(null=False, verbose_name='兑换所需积分数')
    description1 = models.TextField(null=True, blank=True, verbose_name='商品简介1')
    description2 = models.TextField(null=True, blank=True, verbose_name='商品简介2')
    quantity = models.IntegerField(default=0, verbose_name='商品库存数量')
    image_url = models.CharField(max_length=500, null=True, blank=True, verbose_name='商品图片URL')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'products'
        verbose_name = '商品'
        verbose_name_plural = '商品'
        indexes = [
            models.Index(fields=['points_required'], name='idx_products_points'),
        ]

    def __str__(self):
        return f"{self.product_name}({self.points_required}积分)"


class Order(models.Model):
    """订单表"""
    PAYMENT_STATUS_CHOICES = [
        ('pending', '待支付'),
        ('paid', '已支付'),
        ('failed', '支付失败'),
    ]

    order_id = models.AutoField(primary_key=True, verbose_name='订单ID')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name='商品')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='订单下单时间')
    payment_status = models.CharField(
        max_length=10,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending',
        verbose_name='支付状态'
    )
    payment_time = models.DateTimeField(null=True, blank=True, verbose_name='支付时间')

    class Meta:
        db_table = 'orders'
        verbose_name = '订单'
        verbose_name_plural = '订单'
        indexes = [
            models.Index(fields=['payment_status'], name='idx_orders_pay_status'),
            models.Index(fields=['created_at'], name='idx_orders_created'),
        ]

    def __str__(self):
        return f"订单#{self.order_id} - {self.user.username}"


class Report(models.Model):
    """举报信息表"""
    report_id = models.AutoField(primary_key=True, verbose_name='举报ID')
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='举报人')
    report_type = models.CharField(max_length=50, null=False, verbose_name='举报类型')
    reason = models.TextField(null=False, verbose_name='举报原因')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='举报时间')

    class Meta:
        db_table = 'reports'
        verbose_name = '举报信息'
        verbose_name_plural = '举报信息'
        indexes = [
            models.Index(fields=['created_at'], name='idx_reports_created'),
        ]

    def __str__(self):
        return f"举报#{self.report_id} - {self.report_type}"


class ReportProcessing(models.Model):
    """举报处理表"""
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('processed', '已处理')
    ]

    processing_id = models.AutoField(primary_key=True, verbose_name='举报处理ID')
    report = models.ForeignKey(Report, on_delete=models.CASCADE, verbose_name='关联的举报信息ID')
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='处理状态',
        db_column='STATUS'
    )
    processing_result = models.CharField(max_length=1500, default='', verbose_name='处理结果描述(1500字以内)')
    created_at = models.DateTimeField(verbose_name='创建时间(和举报信息表对应id的记录的举报时间相同)')
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name='处理时间')

    class Meta:
        db_table = 'report_processing'
        verbose_name = '举报处理'
        verbose_name_plural = '举报处理'
        indexes = [
            models.Index(fields=['report'], name='idx_report_proc_rid'),
            models.Index(fields=['status'], name='idx_report_proc_status'),
            models.Index(fields=['created_at'], name='idx_report_proc_created'),
        ]

    def __str__(self):
        return f"举报处理 - {self.report.report_type}"


class ReportVideo(models.Model):
    """举报视频表"""
    report_video_id = models.AutoField(primary_key=True, verbose_name='举报视频ID')
    report = models.ForeignKey(Report, on_delete=models.CASCADE, verbose_name='举报信息')
    video_url = models.CharField(max_length=500, null=False, verbose_name='视频URL')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='视频创建时间')

    class Meta:
        db_table = 'report_videos'
        verbose_name = '举报视频'
        verbose_name_plural = '举报视频'
        indexes = [
            models.Index(fields=['report'], name='idx_report_videos_rid'),
        ]

    def __str__(self):
        return f"举报视频 - {self.report.report_type}"


class AbnormalRecord(models.Model):
    """异常记录信息表"""
    abnormal_id = models.AutoField(primary_key=True, verbose_name='异常记录ID')
    abnormal_type = models.CharField(max_length=50, null=False, verbose_name='异常记录类型')
    reason = models.TextField(null=False, verbose_name='异常记录原因')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建异常记录时间')

    class Meta:
        db_table = 'abnormal_records'
        verbose_name = '异常记录信息'
        verbose_name_plural = '异常记录信息'
        indexes = [
            models.Index(fields=['created_at'], name='idx_abnormal_created'),
        ]

    def __str__(self):
        return f"异常记录 - {self.abnormal_type}"


class CameraSession(models.Model):
    """用户主动开启的浏览器摄像头；画面仅在分析期间保存在内存中。"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    browser_session = models.CharField(max_length=64)
    name = models.CharField(max_length=50)
    active = models.BooleanField(default=True)
    last_seen = models.DateTimeField()
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    job_id = models.CharField(max_length=32, blank=True)
    status = models.CharField(max_length=16, default='ready')
    category = models.CharField(max_length=16, blank=True)
    reason = models.CharField(max_length=800, blank=True)
    last_alert_at = models.DateTimeField(null=True, blank=True)
    last_alert_category = models.CharField(max_length=16, blank=True)

    class Meta:
        db_table = 'camera_sessions'
        indexes = [models.Index(fields=['active', 'last_seen'], name='idx_camera_active_seen')]


class AbnormalVideo(models.Model):
    """异常视频表"""
    abnormal_video_id = models.AutoField(primary_key=True, verbose_name='异常视频ID')
    abnormal = models.ForeignKey(AbnormalRecord, on_delete=models.CASCADE, verbose_name='异常记录')
    video_url = models.CharField(max_length=500, null=False, verbose_name='视频URL')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='视频创建时间')

    class Meta:
        db_table = 'abnormal_videos'
        verbose_name = '异常视频'
        verbose_name_plural = '异常视频'
        indexes = [
            models.Index(fields=['abnormal'], name='idx_abnormal_videos_aid'),
        ]

    def __str__(self):
        return f"异常视频 - {self.abnormal.abnormal_type}"


class AbnormalProcessing(models.Model):
    """异常记录处理表"""
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('processed', '已处理')
    ]

    processing_id = models.AutoField(primary_key=True, verbose_name='异常处理ID')
    abnormal = models.ForeignKey(AbnormalRecord, on_delete=models.CASCADE, verbose_name='关联的异常记录ID')
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='处理状态',
        db_column='STATUS'
    )
    processing_description = models.CharField(max_length=1500, default='', verbose_name='处理描述(1500字以内)')
    created_at = models.DateTimeField(verbose_name='创建时间(和异常信息表对应id的激励的创建时间相同)')
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name='处理时间')

    class Meta:
        db_table = 'abnormal_processing'
        verbose_name = '异常记录处理'
        verbose_name_plural = '异常记录处理'
        indexes = [
            models.Index(fields=['abnormal'], name='idx_abnormal_proc_aid'),
            models.Index(fields=['status'], name='idx_abnormal_proc_status'),
            models.Index(fields=['created_at'], name='idx_abnormal_proc_created'),
        ]

    def __str__(self):
        return f"异常处理 - {self.abnormal.abnormal_type}"


class Announcement(models.Model):
    """公告表"""
    TYPE_CHOICES = [
        ('community', '小区公告'),
        ('legal', '普法内容'),
    ]

    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('finalized', '定稿'),
    ]

    announcement_id = models.AutoField(primary_key=True, verbose_name='公告ID')
    title = models.CharField(max_length=200, null=False, verbose_name='公告标题')
    content = models.TextField(null=False, verbose_name='公告内容')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, null=False, verbose_name='公告类型', db_column='TYPE')
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='draft',
        null=False,
        verbose_name='公告状态',
        db_column='STATUS'
    )
    image_url = models.CharField(max_length=500, null=True, blank=True, verbose_name='公告图片url')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='公告创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='公告更新时间')

    class Meta:
        db_table = 'announcements'
        verbose_name = '公告'
        verbose_name_plural = '公告'
        indexes = [
            models.Index(fields=['type', 'status'], name='idx_announce_type_status'),
            models.Index(fields=['created_at'], name='idx_announce_created'),
        ]

    def __str__(self):
        return self.title


# 使用信号实现触发器功能
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


@receiver(post_save, sender=Feedback)
def create_feedback_processing(sender, instance, created, **kwargs):
    """在创建意见反馈时自动创建处理记录"""
    if created:
        FeedbackProcessing.objects.create(
            feedback=instance,
            created_at=instance.created_at
        )


@receiver(post_save, sender=Report)
def create_report_processing(sender, instance, created, **kwargs):
    """在创建举报信息时自动创建处理记录"""
    if created:
        ReportProcessing.objects.create(
            report=instance,
            created_at=instance.created_at
        )


@receiver(post_save, sender=AbnormalRecord)
def create_abnormal_processing(sender, instance, created, **kwargs):
    """在创建异常记录时自动创建处理记录"""
    if created:
        AbnormalProcessing.objects.create(
            abnormal=instance,
            created_at=instance.created_at
        )
