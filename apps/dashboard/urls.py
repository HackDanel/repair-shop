from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.requests, name='requests'),
    path('staff/', views.staff_list, name='staff'),
    path('staff/new/', views.staff_edit, name='staff_create'),
    path('staff/<int:pk>/', views.staff_edit, name='staff_edit'),
    path('clients/', views.clients, name='clients'),
    path('clients/<int:pk>/toggle/', views.toggle_active, name='toggle_active'),
    path('services/', views.service_list, name='services'),
    path('services/new/', views.service_edit, name='service_create'),
    path('services/<int:pk>/', views.service_edit, name='service_edit'),
    path('device-types/new/', views.device_type_create, name='device_type_create'),
    path('stats/', views.statistics, name='stats'),
    path('stats.json', views.statistics_json, name='stats_json'),
]
