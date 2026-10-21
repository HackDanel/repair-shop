from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.permissions import admin_required, staff_required

from . import services
from .forms import AdjustForm, PartForm, ReceiveForm
from .models import Part, StockMovement


@staff_required
def part_list(request):
    query = request.GET.get('q', '').strip()[:100]
    parts = Part.objects.prefetch_related('device_types')
    if query:
        parts = parts.filter(Q(name__icontains=query) | Q(sku__icontains=query))
    if request.GET.get('low'):
        parts = parts.filter(quantity__lte=F('min_quantity'))
    page = Paginator(parts, 25).get_page(request.GET.get('page'))
    low_count = Part.objects.filter(quantity__lte=F('min_quantity')).count()
    return render(request, 'inventory/part_list.html', {
        'page': page, 'query': query, 'low': bool(request.GET.get('low')), 'low_count': low_count,
    })


@admin_required
def part_edit(request, pk=None):
    part = get_object_or_404(Part, pk=pk) if pk else None
    form = PartForm(request.POST if request.method == 'POST' else None, instance=part)
    if request.method == 'POST' and form.is_valid():
        part = form.save()
        messages.success(request, f'Запчасть «{part.name}» сохранена.')
        return redirect('inventory:detail', pk=part.pk)
    return render(request, 'inventory/part_form.html', {'form': form, 'part': part})


@staff_required
def part_detail(request, pk):
    part = get_object_or_404(Part, pk=pk)
    movements = part.movements.select_related('author', 'request')[:50]
    return render(request, 'inventory/part_detail.html', {
        'part': part, 'movements': movements,
        'receive_form': ReceiveForm(), 'adjust_form': AdjustForm(initial={'quantity': part.quantity}),
    })


def _stock_action(func, form_class):
    @require_POST
    @admin_required
    def view(request, pk):
        part = get_object_or_404(Part, pk=pk)
        form = form_class(request.POST)
        if form.is_valid():
            try:
                func(part.pk, form.cleaned_data['quantity'], request.user, form.cleaned_data['note'])
                messages.success(request, 'Остаток обновлён.')
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages))
        else:
            messages.error(request, 'Проверьте количество.')
        return redirect('inventory:detail', pk=part.pk)
    return view


receive = _stock_action(services.receive, ReceiveForm)
adjust = _stock_action(services.adjust, AdjustForm)


@admin_required
def movements(request):
    qs = StockMovement.objects.select_related('part', 'author', 'request')
    kind = request.GET.get('kind', '')
    if kind in StockMovement.Kind.values:
        qs = qs.filter(kind=kind)
    page = Paginator(qs, 50).get_page(request.GET.get('page'))
    return render(request, 'inventory/movements.html', {
        'page': page, 'kind': kind, 'kinds': StockMovement.Kind.choices,
    })
