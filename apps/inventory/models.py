from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Part(models.Model):
    """Запчасть на складе."""
    sku = models.CharField('артикул', max_length=40, unique=True)
    name = models.CharField('название', max_length=150)
    device_types = models.ManyToManyField(
        'catalog.DeviceType', blank=True, related_name='parts', verbose_name='подходит для',
    )
    price = models.DecimalField(
        'цена продажи, ₽', max_digits=10, decimal_places=2, validators=[MinValueValidator(0)],
    )
    quantity = models.PositiveIntegerField('остаток, шт.', default=0)
    min_quantity = models.PositiveIntegerField('минимальный остаток, шт.', default=1)

    class Meta:
        verbose_name = 'запчасть'
        verbose_name_plural = 'запчасти'
        ordering = ['name']
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gte=0), name='part_price_non_negative'),
        ]

    def __str__(self):
        return f'{self.name} [{self.sku}]'

    @property
    def is_low(self):
        return self.quantity <= self.min_quantity


class StockMovement(models.Model):
    """Движение по складу: приход, списание в ремонт, возврат, корректировка."""

    class Kind(models.TextChoices):
        INCOME = 'income', 'Приход'
        USAGE = 'usage', 'Списание в ремонт'
        RETURN = 'return', 'Возврат из ремонта'
        ADJUST = 'adjust', 'Корректировка'

    part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name='movements', verbose_name='запчасть')
    kind = models.CharField('тип', max_length=10, choices=Kind.choices)
    # Положительное значение — поступление на склад, отрицательное — расход.
    delta = models.IntegerField('изменение, шт.')
    request = models.ForeignKey(
        'repairs.RepairRequest', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='stock_movements', verbose_name='заявка',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='кто',
    )
    note = models.CharField('примечание', max_length=200, blank=True)
    created_at = models.DateTimeField('когда', auto_now_add=True)

    class Meta:
        verbose_name = 'движение по складу'
        verbose_name_plural = 'движения по складу'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(condition=~models.Q(delta=0), name='movement_delta_not_zero'),
        ]

    def __str__(self):
        return f'{self.get_kind_display()} {self.delta:+d} — {self.part}'
