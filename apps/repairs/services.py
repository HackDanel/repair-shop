"""Бизнес-операции с заявками. Всё, что меняет склад или статус, идёт через
эти функции, чтобы история и остатки не расходились."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import Part, StockMovement

from .models import Comment, PartUsage, RepairRequest, Status, StatusChange


def can_work_on(user, req):
    """Мастер работает только со своими заявками, администратор — со всеми."""
    return user.is_admin_role or (user.is_master and req.master_id == user.pk)


def can_view(user, req):
    return can_work_on(user, req) or req.client_id == user.pk


def create_request(client, *, photos=(), **fields):
    with transaction.atomic():
        req = RepairRequest.objects.create(client=client, **fields)
        StatusChange.objects.create(request=req, new_status=Status.ACCEPTED, author=client)
        for f in photos:
            req.photos.create(image=f)
    return req


def change_status(req, new_status, user):
    if not can_work_on(user, req):
        raise PermissionDenied
    new_status = Status(new_status)
    # Администратор может исправить любой статус, мастер — только по схеме переходов.
    if not user.is_admin_role and new_status not in req.allowed_statuses():
        raise ValidationError(f'Нельзя перевести заявку из «{req.get_status_display()}» в «{new_status.label}».')
    if new_status == req.status:
        return req
    if new_status == Status.ISSUED and not req.master_id:
        raise ValidationError('Нельзя выдать заявку без назначенного мастера.')
    with transaction.atomic():
        StatusChange.objects.create(request=req, old_status=req.status, new_status=new_status, author=user)
        req.status = new_status
        req.issued_at = timezone.now() if new_status == Status.ISSUED else None
        req.save(update_fields=['status', 'issued_at', 'updated_at'])
    return req


def assign_master(req, master, user):
    if not user.is_admin_role:
        raise PermissionDenied
    if master is not None and not master.is_master:
        raise ValidationError('Назначить можно только пользователя с ролью «Мастер».')
    req.master = master
    req.save(update_fields=['master', 'updated_at'])
    return req


def add_comment(req, user, text, is_internal=False):
    if not can_view(user, req):
        raise PermissionDenied
    # Клиент не может писать внутренние комментарии.
    internal = is_internal and not user.is_client
    return Comment.objects.create(request=req, author=user, text=text, is_internal=internal)


def use_part(req, part_id, quantity, user):
    """Списать запчасть со склада в ремонт."""
    if not can_work_on(user, req):
        raise PermissionDenied
    if req.is_closed:
        raise ValidationError('Заявка уже выдана, менять состав работ нельзя.')
    if quantity < 1:
        raise ValidationError('Количество должно быть не меньше 1.')
    with transaction.atomic():
        # Блокировка строки защищает от гонки, когда два мастера берут последнюю деталь.
        part = Part.objects.select_for_update().get(pk=part_id)
        if part.quantity < quantity:
            raise ValidationError(f'На складе только {part.quantity} шт. «{part.name}».')
        part.quantity -= quantity
        part.save(update_fields=['quantity'])
        StockMovement.objects.create(
            part=part, kind=StockMovement.Kind.USAGE, delta=-quantity, request=req, author=user,
        )
        return PartUsage.objects.create(request=req, part=part, quantity=quantity, unit_price=part.price)


def return_part(usage, user):
    """Отменить списание: вернуть запчасть на склад."""
    req = usage.request
    if not can_work_on(user, req):
        raise PermissionDenied
    if req.is_closed:
        raise ValidationError('Заявка уже выдана, менять состав работ нельзя.')
    with transaction.atomic():
        part = Part.objects.select_for_update().get(pk=usage.part_id)
        part.quantity += usage.quantity
        part.save(update_fields=['quantity'])
        StockMovement.objects.create(
            part=part, kind=StockMovement.Kind.RETURN, delta=usage.quantity, request=req, author=user,
        )
        usage.delete()


def set_labor_cost(req, cost, user):
    if not can_work_on(user, req):
        raise PermissionDenied
    if req.is_closed:
        raise ValidationError('Заявка уже выдана, менять стоимость нельзя.')
    req.labor_cost = cost
    req.save(update_fields=['labor_cost', 'updated_at'])
    return req
