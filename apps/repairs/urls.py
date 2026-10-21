from django.urls import path

from . import views

app_name = 'repairs'

urlpatterns = [
    path('new/', views.create, name='create'),
    path('my/', views.my_list, name='my_list'),
    path('work/', views.master_list, name='master_list'),
    path('<int:pk>/', views.detail, name='detail'),
    path('<int:pk>/status/', views.change_status, name='change_status'),
    path('<int:pk>/comment/', views.add_comment, name='add_comment'),
    path('<int:pk>/parts/', views.use_part, name='use_part'),
    path('<int:pk>/parts/<int:usage_id>/return/', views.return_part, name='return_part'),
    path('<int:pk>/labor/', views.set_labor, name='set_labor'),
    path('<int:pk>/assign/', views.assign, name='assign'),
    path('<int:pk>/photos/<int:photo_id>/', views.photo, name='photo'),
    path('track/<uuid:code>/', views.track, name='track'),
]
