"""Демо-данные: каталог, склад, сотрудники, клиенты и заявки за последний год.

    python manage.py seed_demo            # создать, если база пустая
    python manage.py seed_demo --password Secret123   # свой пароль для демо-учёток
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import DeviceType, Service
from apps.inventory.models import Part, StockMovement
from apps.repairs.models import Comment, PartUsage, RepairRequest, Status, StatusChange

CATALOG = {
    'Смартфон': [
        ('Замена дисплея', 'Оригинальный или совместимый модуль, проверка сенсора.', 3500, 1),
        ('Замена аккумулятора', 'Новая батарея, калибровка контроллера питания.', 1800, 1),
        ('Замена разъёма зарядки', 'Пайка нового разъёма USB-C / Lightning.', 1500, 1),
        ('Восстановление после воды', 'Разборка, чистка платы в ультразвуке, диагностика.', 2500, 3),
        ('Замена камеры', 'Основная или фронтальная камера.', 2200, 2),
    ],
    'Ноутбук': [
        ('Чистка и замена термопасты', 'Разборка, чистка системы охлаждения.', 1500, 1),
        ('Замена матрицы', 'Подбор и установка матрицы.', 4500, 3),
        ('Замена клавиатуры', 'Клавиатура в сборе или отдельно.', 2500, 2),
        ('Апгрейд SSD и ОЗУ', 'Установка комплектующих, перенос системы.', 1000, 1),
        ('Ремонт цепи питания', 'Диагностика и ремонт платы.', 3500, 5),
    ],
    'Планшет': [
        ('Замена стекла / тачскрина', 'Замена сенсорного стекла.', 3000, 2),
        ('Замена аккумулятора', 'Новая батарея.', 2500, 2),
    ],
    'Игровая консоль': [
        ('Чистка и профилактика', 'Чистка, замена термоинтерфейса.', 2000, 1),
        ('Замена HDMI-разъёма', 'Пайка нового порта HDMI.', 3000, 2),
    ],
}

PARTS = [
    ('LCD-IP13', 'Дисплей iPhone 13 (OLED)', ['Смартфон'], 7900, 4, 2),
    ('LCD-SA52', 'Дисплей Samsung A52', ['Смартфон'], 5200, 3, 2),
    ('BAT-IP12', 'Аккумулятор iPhone 12', ['Смартфон'], 1900, 8, 3),
    ('BAT-XRN10', 'Аккумулятор Redmi Note 10', ['Смартфон'], 1300, 6, 3),
    ('USB-C-24P', 'Разъём USB-C 24 pin', ['Смартфон', 'Планшет'], 250, 30, 10),
    ('CAM-IP13', 'Камера основная iPhone 13', ['Смартфон'], 3900, 1, 1),
    ('PASTE-MX4', 'Термопаста Arctic MX-4, 4 г', [], 600, 15, 5),
    ('PAD-1MM', 'Термопрокладка 1 мм', [], 300, 20, 5),
    ('LCD-156FHD', 'Матрица 15.6" FHD IPS 30 pin', ['Ноутбук'], 6500, 3, 1),
    ('KB-LEN-IP5', 'Клавиатура Lenovo IdeaPad 5', ['Ноутбук'], 2900, 2, 1),
    ('SSD-512', 'SSD NVMe 512 ГБ', ['Ноутбук'], 4200, 5, 2),
    ('RAM-16D4', 'ОЗУ SO-DIMM DDR4 16 ГБ', ['Ноутбук'], 3600, 4, 2),
    ('GLS-IPAD9', 'Тачскрин iPad 9', ['Планшет'], 2700, 2, 1),
    ('HDMI-PS5', 'Разъём HDMI PS5', ['Игровая консоль'], 900, 6, 2),
]

MODELS = {
    'Смартфон': ['iPhone 13', 'iPhone 12', 'Samsung Galaxy A52', 'Redmi Note 10', 'Honor 50', 'Pixel 7'],
    'Ноутбук': ['Lenovo IdeaPad 5', 'ASUS VivoBook 15', 'MacBook Air M1', 'HP Pavilion 15', 'Acer Aspire 7'],
    'Планшет': ['iPad 9', 'Galaxy Tab S7', 'Xiaomi Pad 5'],
    'Игровая консоль': ['PlayStation 5', 'Xbox Series S', 'Nintendo Switch'],
}

# Описание неисправности со слов клиента — по услуге из каталога.
PROBLEMS = {
    'Замена дисплея': 'Разбит экран после падения, сенсор работает частично.',
    'Замена аккумулятора': 'Быстро садится батарея, за полдня до нуля.',
    'Замена разъёма зарядки': 'Не заряжается, кабель приходится держать под углом.',
    'Восстановление после воды': 'Упал в воду, после этого не включается.',
    'Замена камеры': 'Камера не фокусируется, на фото пятна.',
    'Чистка и замена термопасты': 'Сильно греется и шумит вентилятор, иногда выключается.',
    'Замена матрицы': 'На экране полосы, в углу тёмное пятно.',
    'Замена клавиатуры': 'Не работают несколько клавиш на клавиатуре.',
    'Апгрейд SSD и ОЗУ': 'Хочу поставить SSD побольше и добавить память.',
    'Ремонт цепи питания': 'Не включается, индикатор зарядки не горит.',
    'Замена стекла / тачскрина': 'Треснуло стекло, тач не реагирует внизу экрана.',
    'Чистка и профилактика': 'Очень шумит и греется во время игры.',
    'Замена HDMI-разъёма': 'Нет сигнала по HDMI, телевизор не видит приставку.',
}
UNKNOWN_PROBLEMS = [
    'Перестал включаться, причина неизвестна.',
    'Периодически перезагружается сам по себе.',
    'Не видит Wi-Fi и Bluetooth.',
]

FIRST = ['Алексей', 'Мария', 'Иван', 'Екатерина', 'Дмитрий', 'Анна', 'Сергей', 'Ольга', 'Павел', 'Наталья',
         'Никита', 'Юлия', 'Артём', 'Светлана', 'Кирилл']
LAST_M = ['Иванов', 'Смирнов', 'Кузнецов', 'Попов', 'Соколов', 'Лебедев', 'Козлов', 'Новиков']
LAST_F = ['Иванова', 'Смирнова', 'Кузнецова', 'Попова', 'Соколова', 'Лебедева', 'Козлова', 'Новикова']


class Command(BaseCommand):
    help = 'Заполнить базу демонстрационными данными'

    def add_arguments(self, parser):
        parser.add_argument('--password', default='demo12345', help='Пароль для всех демо-учёток')
        parser.add_argument('--requests', type=int, default=120)
        parser.add_argument('--seed', type=int, default=42)

    @transaction.atomic
    def handle(self, *args, **opts):
        if RepairRequest.objects.exists() or User.objects.filter(username='admin').exists():
            raise CommandError('В базе уже есть данные — демо-набор не создаётся повторно.')
        rnd = random.Random(opts['seed'])
        pwd = opts['password']

        types = {name: DeviceType.objects.create(name=name) for name in CATALOG}
        services = []
        for tname, items in CATALOG.items():
            for name, descr, price, days in items:
                services.append(Service.objects.create(
                    device_type=types[tname], name=name, description=descr,
                    price_from=Decimal(price), duration_days=days,
                ))

        admin = self._user('admin', 'Елена', 'Орлова', User.Role.ADMIN, pwd, is_staff=True, is_superuser=True)
        masters = [
            self._user('master1', 'Андрей', 'Волков', User.Role.MASTER, pwd),
            self._user('master2', 'Тимур', 'Галиев', User.Role.MASTER, pwd),
            self._user('master3', 'Ксения', 'Белова', User.Role.MASTER, pwd),
        ]
        clients = [self._user('client', 'Пётр', 'Клиентов', User.Role.CLIENT, pwd)]
        for i in range(24):
            female = i % 2
            first = rnd.choice(FIRST[1::2] if female else FIRST[0::2])
            last = rnd.choice(LAST_F if female else LAST_M)
            clients.append(self._user(f'client{i + 1}', first, last, User.Role.CLIENT, pwd))

        parts = {}
        for sku, name, tnames, price, qty, min_qty in PARTS:
            part = Part.objects.create(sku=sku, name=name, price=Decimal(price), quantity=qty + 20, min_quantity=min_qty)
            part.device_types.set([types[t] for t in tnames])
            StockMovement.objects.create(part=part, kind=StockMovement.Kind.INCOME, delta=qty + 20, author=admin,
                                         note='Начальный остаток')
            parts[sku] = part

        now = timezone.now()
        for n in range(opts['requests']):
            tname = rnd.choices(list(CATALOG), weights=[50, 30, 12, 8])[0]
            created = now - timedelta(days=rnd.triangular(0, 360, 20), hours=rnd.randint(0, 10))
            # Чем старее заявка, тем вероятнее, что она уже выдана.
            age = (now - created).days
            if age > 20:
                status = Status.ISSUED
            else:
                status = rnd.choice([Status.ACCEPTED, Status.DIAGNOSTICS, Status.IN_REPAIR, Status.READY, Status.ISSUED])
            service = rnd.choice([s for s in services if s.device_type == types[tname]] + [None])
            req = RepairRequest.objects.create(
                client=rnd.choice(clients), device_type=types[tname], device_model=rnd.choice(MODELS[tname]),
                serial_number=f'SN{rnd.randint(10**7, 10**8 - 1)}', service=service,
                problem=PROBLEMS[service.name] if service else rnd.choice(UNKNOWN_PROBLEMS), status=status,
                master=None if status == Status.ACCEPTED and rnd.random() < .6 else rnd.choice(masters),
                labor_cost=(service.price_from if service else Decimal(1000)) * Decimal(rnd.choice(['1', '1.2', '1.5'])),
            )
            self._history(req, created, status, rnd)
            if status in (Status.IN_REPAIR, Status.READY, Status.ISSUED):
                candidates = [p for p in parts.values()
                              if not p.device_types.exists() or p.device_types.filter(pk=req.device_type_id).exists()]
                for part in rnd.sample(candidates, k=min(len(candidates), rnd.randint(0, 2))):
                    PartUsage.objects.create(request=req, part=part, quantity=1, unit_price=part.price)
                    part.quantity = max(part.quantity - 1, 0)
                    part.save(update_fields=['quantity'])
                    StockMovement.objects.create(part=part, kind=StockMovement.Kind.USAGE, delta=-1,
                                                 request=req, author=req.master)
            if req.master and status != Status.ACCEPTED and rnd.random() < .5:
                comment = Comment.objects.create(
                    request=req, author=req.master,
                    text='Провели диагностику, неисправность подтвердилась. Стоимость согласована.')
                Comment.objects.filter(pk=comment.pk).update(
                    created_at=min(created + timedelta(hours=rnd.randint(5, 30)), now))

        self.stdout.write(self.style.SUCCESS(
            f'Готово: {len(services)} услуг, {len(parts)} запчастей, {len(clients)} клиентов, '
            f'{opts["requests"]} заявок. Логины: admin, master1..3, client; пароль: {pwd}'
        ))

    def _user(self, username, first, last, role, pwd, **extra):
        user = User(username=username, first_name=first, last_name=last, role=role,
                    email=f'{username}@example.com', phone=f'+7913{random.randint(1000000, 9999999)}', **extra)
        user.set_password(pwd)
        user.save()
        return user

    def _history(self, req, created, final, rnd):
        """История статусов и даты: created_at / issued_at ставим задним числом."""
        steps = [Status.ACCEPTED, Status.DIAGNOSTICS, Status.IN_REPAIR, Status.READY, Status.ISSUED]
        upto = steps.index(final)
        when = created
        prev = ''
        for s in steps[:upto + 1]:
            ch = StatusChange.objects.create(request=req, old_status=prev, new_status=s,
                                             author=req.client if s == Status.ACCEPTED else req.master)
            StatusChange.objects.filter(pk=ch.pk).update(created_at=min(when, timezone.now()))
            prev = s
            when += timedelta(hours=rnd.randint(4, 60))
        when = min(when, timezone.now())
        issued = when if final == Status.ISSUED else None
        RepairRequest.objects.filter(pk=req.pk).update(created_at=created, updated_at=when, issued_at=issued)
