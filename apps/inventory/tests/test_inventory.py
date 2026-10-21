from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.tests.factories import make_part, make_user
from apps.inventory import services
from apps.inventory.models import Part, StockMovement


class StockTests(TestCase):
    def setUp(self):
        self.admin = make_user('boss', role=User.Role.ADMIN)
        self.part = make_part(quantity=2)

    def test_receive(self):
        services.receive(self.part.pk, 10, self.admin, 'Поставка')
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 12)
        self.assertEqual(StockMovement.objects.get().delta, 10)

    def test_receive_must_be_positive(self):
        with self.assertRaises(ValidationError):
            services.receive(self.part.pk, 0, self.admin)

    def test_adjust_logs_difference(self):
        services.adjust(self.part.pk, 0, self.admin, 'Брак')
        self.assertEqual(StockMovement.objects.get().delta, -2)
        services.adjust(self.part.pk, 0, self.admin, 'Без изменений')
        self.assertEqual(StockMovement.objects.count(), 1)
        with self.assertRaises(ValidationError):
            services.adjust(self.part.pk, -1, self.admin)

    def test_low_stock_flag(self):
        self.assertFalse(self.part.is_low)
        self.part.quantity = self.part.min_quantity
        self.assertTrue(self.part.is_low)


class StockViewsTests(TestCase):
    def setUp(self):
        self.admin = make_user('boss', role=User.Role.ADMIN)
        self.master = make_user('master', role=User.Role.MASTER)

    def test_master_can_view_but_not_edit(self):
        part = make_part()
        self.client.force_login(self.master)
        self.assertEqual(self.client.get(reverse('inventory:list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('inventory:create')).status_code, 403)
        self.assertEqual(self.client.post(reverse('inventory:receive', args=[part.pk]),
                                          {'quantity': 5, 'note': ''}).status_code, 403)

    def test_client_has_no_access(self):
        self.client.force_login(make_user('c'))
        self.assertEqual(self.client.get(reverse('inventory:list')).status_code, 403)

    def test_create_part_normalizes_sku_and_rejects_duplicates(self):
        self.client.force_login(self.admin)
        data = {'sku': ' bat-01 ', 'name': 'Батарея', 'price': '1200', 'quantity': 4, 'min_quantity': 1}
        self.client.post(reverse('inventory:create'), data)
        self.assertTrue(Part.objects.filter(sku='BAT-01').exists())
        resp = self.client.post(reverse('inventory:create'), data)
        self.assertIn('sku', resp.context['form'].errors)

    def test_negative_price_rejected(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('inventory:create'),
                                {'sku': 'X', 'name': 'X', 'price': '-1', 'quantity': 1, 'min_quantity': 1})
        self.assertIn('price', resp.context['form'].errors)

    def test_edit_does_not_change_quantity(self):
        part = make_part(quantity=7)
        self.client.force_login(self.admin)
        self.client.post(reverse('inventory:edit', args=[part.pk]),
                         {'sku': part.sku, 'name': 'Новое имя', 'price': '1', 'quantity': 999, 'min_quantity': 1})
        part.refresh_from_db()
        self.assertEqual((part.name, part.quantity), ('Новое имя', 7))

    def test_low_filter(self):
        make_part('A', quantity=0)
        make_part('B', quantity=50)
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('inventory:list'), {'low': '1'})
        self.assertEqual([p.sku for p in resp.context['page']], ['A'])
