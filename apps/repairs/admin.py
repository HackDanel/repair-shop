from django.contrib import admin

from .models import Comment, PartUsage, Photo, RepairRequest, StatusChange


class PhotoInline(admin.TabularInline):
    model = Photo
    extra = 0


class PartUsageInline(admin.TabularInline):
    model = PartUsage
    extra = 0


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0


class StatusChangeInline(admin.TabularInline):
    model = StatusChange
    extra = 0
    readonly_fields = ['old_status', 'new_status', 'author', 'created_at']


@admin.register(RepairRequest)
class RepairRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'device_type', 'device_model', 'status', 'master', 'created_at']
    list_filter = ['status', 'device_type', 'master']
    search_fields = ['device_model', 'serial_number', 'client__last_name', 'client__email']
    inlines = [PhotoInline, PartUsageInline, CommentInline, StatusChangeInline]
