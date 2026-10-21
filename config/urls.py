from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('', include('apps.catalog.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('requests/', include('apps.repairs.urls')),
    path('stock/', include('apps.inventory.urls')),
    path('manage/', include('apps.dashboard.urls')),
    path('django-admin/', admin.site.urls),
]

admin.site.site_header = 'Ремонтная мастерская — администрирование'
