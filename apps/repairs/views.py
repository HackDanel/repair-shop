from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.permissions import client_required, staff_required

from . import services
from .forms import AssignForm, CommentForm, LaborCostForm, PartUsageForm, RepairRequestForm, StatusForm
from .models import STATUS_ORDER, Photo, RepairRequest, Status


def _first_error(form):
    return next(iter(e for errs in form.errors.values() for e in errs), 'Проверьте введённые данные.')


@client_required
def create(request):
    initial = {}
    service_id = request.GET.get('service', '')
    if service_id.isdigit():
        from apps.catalog.models import Service
        service = Service.objects.filter(pk=service_id, is_active=True).first()
        if service:
            initial = {'service': service, 'device_type': service.device_type}
    form = RepairRequestForm(request.POST if request.method == 'POST' else None, request.FILES if request.method == 'POST' else None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        req = services.create_request(
            request.user,
            photos=data['photos'],
            device_type=data['device_type'],
            device_model=data['device_model'],
            serial_number=data['serial_number'],
            service=data['service'],
            problem=data['problem'],
        )
        messages.success(request, f'Заявка №{req.number} принята. Мы сообщим, когда мастер начнёт диагностику.')
        return redirect('repairs:detail', pk=req.pk)
    return render(request, 'repairs/create.html', {'form': form})


@client_required
def my_list(request):
    qs = request.user.requests.select_related('device_type', 'master')
    active = qs.exclude(status=Status.ISSUED)
    history = qs.filter(status=Status.ISSUED).prefetch_related('part_usages')
    return render(request, 'repairs/my_list.html', {'active': active, 'history': history})


@staff_required
def master_list(request):
    qs = RepairRequest.objects.select_related('device_type', 'client')
    if not request.user.is_admin_role:
        qs = qs.filter(master=request.user)
    status = request.GET.get('status', '')
    if status in STATUS_ORDER:
        qs = qs.filter(status=status)
    else:
        qs = qs.exclude(status=Status.ISSUED)
    page = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'repairs/master_list.html', {
        'page': page, 'status': status, 'statuses': Status.choices,
    })


def _get_visible(request, pk):
    req = get_object_or_404(
        RepairRequest.objects.select_related('client', 'master', 'device_type', 'service'), pk=pk,
    )
    if not services.can_view(request.user, req):
        # 404 вместо 403: не подтверждаем, что заявка с таким номером существует.
        raise Http404
    return req


@login_required
def detail(request, pk):
    req = _get_visible(request, pk)
    user = request.user
    can_work = services.can_work_on(user, req)
    comments = req.comments.select_related('author')
    if user.is_client:
        comments = comments.filter(is_internal=False)
    ctx = {
        'req': req,
        'can_work': can_work,
        'comments': comments,
        'history': req.status_changes.select_related('author'),
        'usages': req.part_usages.select_related('part'),
        'photos': req.photos.all(),
        'steps': Status.choices,
        'comment_form': CommentForm(),
    }
    if can_work and not req.is_closed:
        ctx['status_form'] = StatusForm(request_obj=req, user=user)
        ctx['part_form'] = PartUsageForm(device_type=req.device_type)
        ctx['labor_form'] = LaborCostForm(initial={'labor_cost': req.labor_cost})
    if user.is_admin_role:
        ctx['assign_form'] = AssignForm(initial={'master': req.master})
    return render(request, 'repairs/detail.html', ctx)


def _action(view):
    """Общая обвязка POST-действий над заявкой: доступ, ошибки, редирект обратно."""

    @require_POST
    @login_required
    def wrapper(request, pk, *args, **kwargs):
        req = _get_visible(request, pk)
        try:
            msg = view(request, req, *args, **kwargs)
            if msg:
                messages.success(request, msg)
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages))
        except PermissionDenied:
            messages.error(request, 'Недостаточно прав для этого действия.')
        return redirect('repairs:detail', pk=req.pk)
    return wrapper


@_action
def change_status(request, req):
    form = StatusForm(request.POST, request_obj=req, user=request.user)
    if not form.is_valid():
        raise ValidationError(_first_error(form))
    services.change_status(req, form.cleaned_data['status'], request.user)
    return f'Статус изменён: {req.get_status_display()}.'


@_action
def add_comment(request, req):
    form = CommentForm(request.POST)
    if not form.is_valid():
        raise ValidationError(_first_error(form))
    services.add_comment(req, request.user, form.cleaned_data['text'], form.cleaned_data['is_internal'])
    return 'Комментарий добавлен.'


@_action
def use_part(request, req):
    form = PartUsageForm(request.POST, device_type=req.device_type)
    if not form.is_valid():
        raise ValidationError(_first_error(form))
    usage = services.use_part(req, form.cleaned_data['part'].pk, form.cleaned_data['quantity'], request.user)
    return f'Списано: {usage.part.name} × {usage.quantity}.'


@_action
def return_part(request, req, usage_id):
    usage = get_object_or_404(req.part_usages, pk=usage_id)
    services.return_part(usage, request.user)
    return 'Запчасть возвращена на склад.'


@_action
def set_labor(request, req):
    form = LaborCostForm(request.POST)
    if not form.is_valid():
        raise ValidationError(_first_error(form))
    services.set_labor_cost(req, form.cleaned_data['labor_cost'], request.user)
    return 'Стоимость работ сохранена.'


@_action
def assign(request, req):
    form = AssignForm(request.POST)
    if not form.is_valid():
        raise ValidationError(_first_error(form))
    services.assign_master(req, form.cleaned_data['master'], request.user)
    return f'Мастер: {req.master or "не назначен"}.'


@login_required
def photo(request, pk, photo_id):
    """Фото отдаются только тем, кто видит заявку, а не напрямую из /media/."""
    req = _get_visible(request, pk)
    obj = get_object_or_404(Photo, pk=photo_id, request=req)
    return FileResponse(obj.image.open('rb'))


def track(request, code):
    """Публичная проверка статуса по коду из квитанции — без логина, без личных данных."""
    req = get_object_or_404(RepairRequest.objects.select_related('device_type'), tracking_code=code)
    return render(request, 'repairs/track.html', {'req': req, 'steps': Status.choices})
