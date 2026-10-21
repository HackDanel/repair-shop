from django.contrib import admin

from .models import Part, StockMovement


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ['sku', 'name', 'price', 'quantity', 'min_quantity']
    search_fields = ['sku', 'name']
    filter_horizontal = ['device_types']


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'part', 'kind', 'delta', 'request', 'author']
    list_filter = ['kind']
