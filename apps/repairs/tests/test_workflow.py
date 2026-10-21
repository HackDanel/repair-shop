from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.tests.factories import make_catalog, make_part, make_user
from apps.inventory.models import StockMovement
from apps.repairs import services
from apps.repairs.models import RepairRequest, Status


class WorkflowTests(TestCase):
    def setUp(self):
        self.phone, self.laptop, _ = make_catalog()
        self.owner = make_user('owner')
        self.master = make_user('master', role=User.Role.MASTER)
        self.admin = make_user('boss', role=User.Role.ADMIN)
        self.req = services.create_request(self.owner, device_type=self.phone, device_model='X',
                                           problem='Не включается вообще')
        services.assign_master(self.req, self.master, self.admin)

    def walk(self, *statuses, user=None):
        for s in statuses:
            services.change_status(self.req, s, user or self.master)

    def test_full_happy_path(self):
        self.walk(Status.DIAGNOSTICS, Status.IN_REPAIR, Status.READY, Status.ISSUED)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, Status.ISSUED)
        self.assertIsNotNone(self.req.issued_at)
        history = list(self.req.status_changes.values_list('new_status', flat=True))
        self.assertEqual(history, ['accepted', 'diagnostics', 'in_repair', 'ready', 'issued'])

    def test_master_cannot_skip_steps(self):
        with self.assertRaises(ValidationError):
            self.walk(Status.READY)
        with self.assertRaises(ValidationError):
            self.walk(Status.ISSUED)

    def test_issued_is_final_for_master(self):
        self.walk(Status.DIAGNOSTICS, Status.READY, Status.ISSUED)
        with self.assertRaises(ValidationError):
            self.walk(Status.READY)

    def test_admin_can_set_any_status_and_reopen(self):
        self.walk(Status.READY, user=self.admin)
        self.walk(Status.ISSUED, user=self.admin)
        self.walk(Status.IN_REPAIR, user=self.admin)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, Status.IN_REPAIR)
        self.assertIsNone(self.req.issued_at)

    def test_cannot_issue_without_master(self):
        services.assign_master(self.req, None, self.admin)
        with self.assertRaises(ValidationError):
            self.walk(Status.ISSUED, user=self.admin)

    def test_foreign_master_cannot_work(self):
        stranger = make_user('m2', role=User.Role.MASTER)
        with self.assertRaises(PermissionDenied):
            services.change_status(self.req, Status.DIAGNOSTICS, stranger)
        with self.assertRaises(PermissionDenied):
            services.set_labor_cost(self.req, Decimal('100'), stranger)

    def test_only_admin_assigns_and_only_masters(self):
        with self.assertRaises(PermissionDenied):
            services.assign_master(self.req, self.master, self.master)
        with self.assertRaises(ValidationError):
            services.assign_master(self.req, self.owner, self.admin)

    def test_status_change_via_http(self):
        self.client.force_login(self.master)
        url = reverse('repairs:change_status', args=[self.req.pk])
        self.client.post(url, {'status': Status.DIAGNOSTICS})
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, Status.DIAGNOSTICS)
        # Недопустимый переход не применяется, пользователь видит ошибку.
        resp = self.client.post(url, {'status': Status.ISSUED}, follow=True)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, Status.DIAGNOSTICS)
        self.assertContains(resp, 'msg--error')


class PartsTests(TestCase):
    def setUp(self):
        phone, _, _ = make_catalog()
        self.master = make_user('master', role=User.Role.MASTER)
        self.req = RepairRequest.objects.create(client=make_user('owner'), device_type=phone, device_model='X',
                                                problem='y' * 10, master=self.master, labor_cost=Decimal('1500'))
        self.part = make_part(quantity=3, price='700', device_type=phone)

    def test_use_part_decrements_stock_and_logs(self):
        usage = services.use_part(self.req, self.part.pk, 2, self.master)
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 1)
        self.assertEqual(usage.unit_price, Decimal('700'))
        mv = StockMovement.objects.get()
        self.assertEqual((mv.kind, mv.delta, mv.request), (StockMovement.Kind.USAGE, -2, self.req))
        self.assertEqual(self.req.total_cost, Decimal('2900'))

    def test_cannot_take_more_than_in_stock(self):
        services.use_part(self.req, self.part.pk, 3, self.master)  # ровно весь остаток — можно
        with self.assertRaises(ValidationError):
            services.use_part(self.req, self.part.pk, 1, self.master)
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 0)

    def test_zero_quantity_rejected(self):
        with self.assertRaises(ValidationError):
            services.use_part(self.req, self.part.pk, 0, self.master)

    def test_price_fixed_at_usage_time(self):
        services.use_part(self.req, self.part.pk, 1, self.master)
        self.part.price = Decimal('9999')
        self.part.save()
        self.assertEqual(self.req.parts_cost, Decimal('700'))

    def test_return_part_restores_stock(self):
        usage = services.use_part(self.req, self.part.pk, 2, self.master)
        services.return_part(usage, self.master)
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 3)
        self.assertFalse(self.req.part_usages.exists())
        self.assertEqual(sorted(StockMovement.objects.values_list('delta', flat=True)), [-2, 2])

    def test_closed_request_is_locked(self):
        self.req.status = Status.ISSUED
        self.req.save()
        with self.assertRaises(ValidationError):
            services.use_part(self.req, self.part.pk, 1, self.master)
        with self.assertRaises(ValidationError):
            services.set_labor_cost(self.req, Decimal('1'), self.master)

    def test_labor_cost_validation_via_http(self):
        self.client.force_login(self.master)
        url = reverse('repairs:set_labor', args=[self.req.pk])
        for value, expected in [('-1', '1500.00'), ('abc', '1500.00'), ('0', '0.00'), ('1000000', '1000000.00'),
                                ('1000000.01', '1000000.00')]:
            self.client.post(url, {'labor_cost': value})
            self.req.refresh_from_db()
            self.assertEqual(str(self.req.labor_cost), expected, value)

    def test_use_part_via_http_shows_error_when_short(self):
        self.client.force_login(self.master)
        resp = self.client.post(reverse('repairs:use_part', args=[self.req.pk]),
                                {'part': self.part.pk, 'quantity': 5}, follow=True)
        self.assertContains(resp, 'На складе только 3')
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 3)
