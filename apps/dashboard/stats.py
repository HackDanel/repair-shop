"""Расчёт показателей для страницы статистики."""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.accounts.models import User
from apps.repairs.models import PartUsage, RepairRequest, Status

MONTHS = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']


def _month_keys(count):
    """Первые числа последних `count` месяцев, от старого к новому."""
    today = timezone.localdate().replace(day=1)
    keys = []
    year, month = today.year, today.month
    for _ in range(count):
        keys.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(keys))


def _by_month(qs, field, value, months):
    rows = (qs.annotate(m=TruncMonth(field)).values('m').annotate(v=value).order_by('m'))
    data = {(r['m'].year, r['m'].month): r['v'] or 0 for r in rows if r['m']}
    return [data.get(k, 0) for k in months]


def collect(months=12):
    keys = _month_keys(months)
    since = timezone.make_aware(timezone.datetime(keys[0][0], keys[0][1], 1))
    labels = [f'{MONTHS[m - 1]} {str(y)[2:]}' for y, m in keys]

    created = RepairRequest.objects.filter(created_at__gte=since)
    issued = RepairRequest.objects.filter(status=Status.ISSUED, issued_at__gte=since)

    requests_per_month = _by_month(created, 'created_at', Count('id'), keys)
    labor = _by_month(issued, 'issued_at', Sum('labor_cost'), keys)
    parts = _by_month(
        PartUsage.objects.filter(request__in=issued), 'request__issued_at',
        Sum(F('quantity') * F('unit_price')), keys,
    )
    revenue = [float(Decimal(a) + Decimal(b)) for a, b in zip(labor, parts)]

    problems = (
        RepairRequest.objects.values('service__name')
        .annotate(n=Count('id')).order_by('-n')[:8]
    )
    devices = RepairRequest.objects.values('device_type__name').annotate(n=Count('id')).order_by('-n')

    masters = (
        User.objects.filter(role=User.Role.MASTER, is_active=True)
        .annotate(
            active=Count('assigned_requests', filter=~Q(assigned_requests__status=Status.ISSUED)),
            done=Count('assigned_requests', filter=Q(
                assigned_requests__status=Status.ISSUED,
                assigned_requests__issued_at__gte=timezone.now() - timedelta(days=30),
            )),
        ).order_by('last_name')
    )

    avg_days = RepairRequest.objects.filter(status=Status.ISSUED, issued_at__isnull=False).aggregate(
        d=Avg(ExpressionWrapper(F('issued_at') - F('created_at'), output_field=DurationField())),
    )['d']

    by_status = dict(RepairRequest.objects.values_list('status').annotate(n=Count('id')))

    return {
        'kpi': {
            'active': sum(n for s, n in by_status.items() if s != Status.ISSUED),
            'ready': by_status.get(Status.READY, 0),
            'unassigned': RepairRequest.objects.filter(master__isnull=True).exclude(status=Status.ISSUED).count(),
            'revenue_month': revenue[-1],
            'avg_days': round(avg_days.total_seconds() / 86400, 1) if avg_days else None,
        },
        'charts': {
            'months': labels,
            'requests': requests_per_month,
            'revenue': revenue,
            'problems': {
                'labels': [p['service__name'] or 'Без услуги (диагностика)' for p in problems],
                'values': [p['n'] for p in problems],
            },
            'devices': {
                'labels': [d['device_type__name'] for d in devices],
                'values': [d['n'] for d in devices],
            },
            'masters': {
                'labels': [str(m) for m in masters],
                'active': [m.active for m in masters],
                'done': [m.done for m in masters],
            },
            'statuses': {
                'labels': [s.label for s in Status],
                'values': [by_status.get(s.value, 0) for s in Status],
            },
        },
    }

