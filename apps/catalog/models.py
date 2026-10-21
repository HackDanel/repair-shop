from django.core.validators import MinValueValidator
from django.db import models


class DeviceType(models.Model):
    """Тип устройства: смартфон, ноутбук, планшет..."""
    name = models.CharField('название', max_length=60, unique=True)

    class Meta:
        verbose_name = 'тип устройства'
        verbose_name_plural = 'типы устройств'
        ordering = ['name']

    def __str__(self):
        return self.name


class Service(models.Model):
    """Услуга каталога с ориентировочной ценой «от»."""
    device_type = models.ForeignKey(
        DeviceType, on_delete=models.PROTECT, related_name='services', verbose_name='тип устройства',
    )
    name = models.CharField('название', max_length=120)
    description = models.TextField('описание', blank=True)
    price_from = models.DecimalField(
        'цена от, ₽', max_digits=10, decimal_places=2, validators=[MinValueValidator(0)],
    )
    duration_days = models.PositiveSmallIntegerField(
        'срок, дней', default=1, validators=[MinValueValidator(1)],
    )
    is_active = models.BooleanField('показывать в каталоге', default=True)

    class Meta:
        verbose_name = 'услуга'
        verbose_name_plural = 'услуги'
        ordering = ['device_type__name', 'name']
        constraints = [
            models.UniqueConstraint(fields=['device_type', 'name'], name='uniq_service_per_device'),
            models.CheckConstraint(condition=models.Q(price_from__gte=0), name='service_price_non_negative'),
        ]

    def __str__(self):
        return f'{self.name} ({self.device_type})'
