"""Простые фабрики тестовых данных, общие для всех приложений."""
from decimal import Decimal

from apps.accounts.models import User
from apps.catalog.models import DeviceType, Service
from apps.inventory.models import Part

PASSWORD = 'Str0ng-pass-42'


def make_user(username, role=User.Role.CLIENT, **extra):
    user = User(username=username, email=f'{username}@test.local', role=role,
                first_name=username.capitalize(), last_name='Тестов', **extra)
    user.set_password(PASSWORD)
    user.save()
    return user


def make_catalog():
    phone = DeviceType.objects.create(name='Смартфон')
    laptop = DeviceType.objects.create(name='Ноутбук')
    screen = Service.objects.create(device_type=phone, name='Замена дисплея', price_from=Decimal('3500'))
    return phone, laptop, screen


def make_part(sku='P-1', quantity=5, price='1000', device_type=None):
    part = Part.objects.create(sku=sku, name=f'Деталь {sku}', price=Decimal(price), quantity=quantity, min_quantity=1)
    if device_type:
        part.device_types.add(device_type)
    return part
