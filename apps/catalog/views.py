from django.db.models import Prefetch, Q
from django.shortcuts import render

from .models import DeviceType, Service


def index(request):
    query = request.GET.get('q', '').strip()[:100]
    device = request.GET.get('device', '')

    services = Service.objects.filter(is_active=True)
    if query:
        services = services.filter(Q(name__icontains=query) | Q(description__icontains=query))
    types = DeviceType.objects.all()
    if device.isdigit():
        types = types.filter(pk=device)
    types = types.prefetch_related(Prefetch('services', queryset=services, to_attr='visible_services'))
    groups = [t for t in types if t.visible_services]

    return render(request, 'catalog/index.html', {
        'groups': groups,
        'device_types': DeviceType.objects.all(),
        'query': query,
        'device': device,
    })
