from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.forms import StaffForm
from apps.accounts.models import User
from apps.accounts.permissions import admin_required
from apps.catalog.models import DeviceType, Service
from apps.repairs.models import STATUS_ORDER, RepairRequest, Status

from . import stats
from .forms import DeviceTypeForm, ServiceForm


@admin_required
def requests(request):
    qs = RepairRequest.objects.select_related('client', 'master', 'device_type')
    status = request.GET.get('status', '')
    master = request.GET.get('master', '')
    query = request.GET.get('q', '').strip()[:100]
    if status in STATUS_ORDER:
        qs = qs.filter(status=status)
    elif status == 'open':
        qs = qs.exclude(status=Status.ISSUED)
    if master == 'none':
        qs = qs.filter(master__isnull=True)
    elif master.isdigit():
        qs = qs.filter(master_id=master)
    if query:
        filters = (Q(device_model__icontains=query) | Q(serial_number__icontains=query)
                   | Q(client__last_name__icontains=query) | Q(client__email__icontains=query)
                   | Q(client__phone__icontains=query))
        if query.isdigit():
            filters |= Q(pk=int(query))
        qs = qs.filter(filters)
    page = Paginator(qs, 25).get_page(request.GET.get('page'))
    return render(request, 'dashboard/requests.html', {
        'page': page, 'status': status, 'master': master, 'query': query,
        'statuses': Status.choices, 'masters': User.objects.filter(role=User.Role.MASTER),
    })


@admin_required
def staff_list(request):
    staff = User.objects.filter(role__in=[User.Role.MASTER, User.Role.ADMIN]).annotate(
        active_requests=Count('assigned_requests', filter=~Q(assigned_requests__status=Status.ISSUED)),
    ).order_by('role', 'last_name')
    return render(request, 'dashboard/staff_list.html', {'staff': staff})


@admin_required
def staff_edit(request, pk=None):
    # Здесь редактируются только сотрудники: иначе через форму можно сменить пароль клиенту.
    obj = get_object_or_404(User, pk=pk, role__in=[User.Role.MASTER, User.Role.ADMIN]) if pk else None
    if obj is not None and obj.is_superuser and not request.user.is_superuser:
        raise PermissionDenied
    form = StaffForm(request.POST if request.method == 'POST' else None, instance=obj,
                     initial=None if obj else {'role': User.Role.MASTER})
    if request.method == 'POST' and form.is_valid():
        if obj == request.user and (not form.cleaned_data['is_active']
                                    or form.cleaned_data['role'] != User.Role.ADMIN):
            # Иначе администратор может случайно лишить себя доступа к панели.
            form.add_error(None, 'Нельзя отключить или понизить свою собственную учётную запись.')
        else:
            user = form.save()
            messages.success(request, f'Сотрудник {user} сохранён.')
            return redirect('dashboard:staff')
    return render(request, 'dashboard/staff_form.html', {'form': form, 'obj': obj})


@admin_required
def clients(request):
    query = request.GET.get('q', '').strip()[:100]
    qs = User.objects.filter(role=User.Role.CLIENT).annotate(n=Count('requests')).order_by('last_name', 'first_name')
    if query:
        qs = qs.filter(Q(last_name__icontains=query) | Q(email__icontains=query) | Q(phone__icontains=query))
    page = Paginator(qs, 25).get_page(request.GET.get('page'))
    return render(request, 'dashboard/clients.html', {'page': page, 'query': query})


@require_POST
@admin_required
def toggle_active(request, pk):
    user = get_object_or_404(User, pk=pk, role=User.Role.CLIENT)
    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])
    messages.success(request, f'{user}: {"разблокирован" if user.is_active else "заблокирован"}.')
    return redirect('dashboard:clients')


@admin_required
def service_list(request):
    return render(request, 'dashboard/service_list.html', {
        'services': Service.objects.select_related('device_type'),
        'device_types': DeviceType.objects.annotate(n=Count('services')),
        'type_form': DeviceTypeForm(),
    })


@admin_required
def service_edit(request, pk=None):
    obj = get_object_or_404(Service, pk=pk) if pk else None
    form = ServiceForm(request.POST if request.method == 'POST' else None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        service = form.save()
        messages.success(request, f'Услуга «{service.name}» сохранена.')
        return redirect('dashboard:services')
    return render(request, 'dashboard/service_form.html', {'form': form, 'obj': obj})


@require_POST
@admin_required
def device_type_create(request):
    form = DeviceTypeForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, 'Тип устройства добавлен.')
    else:
        messages.error(request, ' '.join(form.errors.get('name', ['Проверьте название.'])))
    return redirect('dashboard:services')


@admin_required
def statistics(request):
    return render(request, 'dashboard/statistics.html', {'data': stats.collect()})


@admin_required
def statistics_json(request):
    return JsonResponse(stats.collect())
