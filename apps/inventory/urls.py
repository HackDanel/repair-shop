from django.urls import path

from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.part_list, name='list'),
    path('new/', views.part_edit, name='create'),
    path('movements/', views.movements, name='movements'),
    path('<int:pk>/', views.part_detail, name='detail'),
    path('<int:pk>/edit/', views.part_edit, name='edit'),
    path('<int:pk>/receive/', views.receive, name='receive'),
    path('<int:pk>/adjust/', views.adjust, name='adjust'),
]
