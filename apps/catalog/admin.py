from django.contrib import admin

from .models import DeviceType, Service


@admin.register(DeviceType)
class DeviceTypeAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'device_type', 'price_from', 'duration_days', 'is_active']
    list_filter = ['device_type', 'is_active']
    search_fields = ['name']
