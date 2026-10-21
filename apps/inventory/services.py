from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Part, StockMovement


def receive(part_id, quantity, user, note=''):
    """Приход запчастей на склад."""
    if quantity < 1:
        raise ValidationError('Количество прихода должно быть не меньше 1.')
    with transaction.atomic():
        part = Part.objects.select_for_update().get(pk=part_id)
        part.quantity += quantity
        part.save(update_fields=['quantity'])
        StockMovement.objects.create(part=part, kind=StockMovement.Kind.INCOME, delta=quantity, author=user, note=note)
    return part


def adjust(part_id, new_quantity, user, note=''):
    """Инвентаризация: выставить фактический остаток."""
    if new_quantity < 0:
        raise ValidationError('Остаток не может быть отрицательным.')
    with transaction.atomic():
        part = Part.objects.select_for_update().get(pk=part_id)
        delta = new_quantity - part.quantity
        if delta == 0:
            return part
        part.quantity = new_quantity
        part.save(update_fields=['quantity'])
        StockMovement.objects.create(part=part, kind=StockMovement.Kind.ADJUST, delta=delta, author=user, note=note)
    return part
