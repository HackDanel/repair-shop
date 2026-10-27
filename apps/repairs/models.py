import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Sum


class Status(models.TextChoices):
    ACCEPTED = 'accepted', 'Принята'
    DIAGNOSTICS = 'diagnostics', 'В диагностике'
    IN_REPAIR = 'in_repair', 'В ремонте'
    READY = 'ready', 'Готова к выдаче'
    ISSUED = 'issued', 'Выдана'


# Допустимые переходы статусов. Шаг назад разрешён, чтобы исправить ошибку
# (например, после диагностики понадобилась повторная), «Выдана» — конечный.
TRANSITIONS = {
    Status.ACCEPTED: [Status.DIAGNOSTICS],
    Status.DIAGNOSTICS: [Status.ACCEPTED, Status.IN_REPAIR, Status.READY],
    Status.IN_REPAIR: [Status.DIAGNOSTICS, Status.READY],
    Status.READY: [Status.IN_REPAIR, Status.ISSUED],
    Status.ISSUED: [],
}

STATUS_ORDER = [s.value for s in Status]


class RepairRequest(models.Model):
    tracking_code = models.UUIDField('код отслеживания', default=uuid.uuid4, unique=True, editable=False)
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='requests', verbose_name='клиент',
        limit_choices_to={'role': 'client'},
    )
    device_type = models.ForeignKey(
        'catalog.DeviceType', on_delete=models.PROTECT, related_name='requests', verbose_name='тип устройства',
    )
    device_model = models.CharField('модель устройства', max_length=120)
    serial_number = models.CharField('серийный номер / IMEI', max_length=60, blank=True)
    service = models.ForeignKey(
        'catalog.Service', on_delete=models.SET_NULL, null=True, blank=True, related_name='requests',
        verbose_name='услуга из каталога',
    )
    problem = models.TextField('описание неисправности')
    status = models.CharField('статус', max_length=12, choices=Status.choices, default=Status.ACCEPTED)
    master = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_requests', verbose_name='мастер', limit_choices_to={'role': 'master'},
    )
    labor_cost = models.DecimalField(
        'стоимость работ, ₽', max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)],
    )
    created_at = models.DateTimeField('создана', auto_now_add=True)
    updated_at = models.DateTimeField('изменена', auto_now=True)
    issued_at = models.DateTimeField('выдана', null=True, blank=True)

    class Meta:
        verbose_name = 'заявка на ремонт'
        verbose_name_plural = 'заявки на ремонт'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status']), models.Index(fields=['created_at'])]
        constraints = [
            models.CheckConstraint(condition=models.Q(labor_cost__gte=0), name='request_labor_non_negative'),
        ]

    def __str__(self):
        return f'Заявка №{self.pk} — {self.device_type} {self.device_model}'

    @property
    def number(self):
        return f'{self.pk:06d}'

    @property
    def parts_cost(self):
        # В списках запчасти подгружаются prefetch_related — тогда считаем без запроса на каждую заявку.
        prefetched = getattr(self, '_prefetched_objects_cache', {}).get('part_usages')
        if prefetched is not None:
            return sum((u.total for u in prefetched), Decimal('0'))
        total = self.part_usages.aggregate(s=Sum(F('quantity') * F('unit_price')))['s']
        return total or Decimal('0')

    @property
    def total_cost(self):
        return self.labor_cost + self.parts_cost

    @property
    def status_step(self):
        return STATUS_ORDER.index(self.status)

    @property
    def is_closed(self):
        return self.status == Status.ISSUED

    def allowed_statuses(self):
        return TRANSITIONS[Status(self.status)]


class StatusChange(models.Model):
    """История смены статусов: кто, когда и из какого в какой."""
    request = models.ForeignKey(RepairRequest, on_delete=models.CASCADE, related_name='status_changes')
    old_status = models.CharField('было', max_length=12, choices=Status.choices, blank=True)
    new_status = models.CharField('стало', max_length=12, choices=Status.choices)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'смена статуса'
        verbose_name_plural = 'история статусов'


class Comment(models.Model):
    request = models.ForeignKey(RepairRequest, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    text = models.TextField('комментарий', max_length=2000)
    # Внутренний комментарий видят только мастер и администратор.
    is_internal = models.BooleanField('только для сотрудников', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'комментарий'
        verbose_name_plural = 'комментарии'


def photo_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    return f'requests/{instance.request_id}/{uuid.uuid4().hex}.{ext}'


class Photo(models.Model):
    request = models.ForeignKey(RepairRequest, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField('фото', upload_to=photo_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'фото'
        verbose_name_plural = 'фото'


class PartUsage(models.Model):
    """Запчасть, использованная в ремонте. Цена фиксируется на момент списания."""
    request = models.ForeignKey(RepairRequest, on_delete=models.CASCADE, related_name='part_usages')
    part = models.ForeignKey('inventory.Part', on_delete=models.PROTECT, related_name='usages', verbose_name='запчасть')
    quantity = models.PositiveIntegerField('количество', validators=[MinValueValidator(1)])
    unit_price = models.DecimalField('цена за шт., ₽', max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'использованная запчасть'
        verbose_name_plural = 'использованные запчасти'
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name='usage_quantity_positive'),
        ]

    @property
    def total(self):
        return self.quantity * self.unit_price
