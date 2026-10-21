from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.tests.factories import make_catalog
from apps.catalog.models import Service


class CatalogTests(TestCase):
    def setUp(self):
        self.phone, self.laptop, self.screen = make_catalog()
        Service.objects.create(device_type=self.laptop, name='Чистка ноутбука', price_from=Decimal('1500'))

    def test_public_and_grouped(self):
        resp = self.client.get(reverse('catalog:index'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([g.name for g in resp.context['groups']], ['Ноутбук', 'Смартфон'])

    def test_search(self):
        resp = self.client.get(reverse('catalog:index'), {'q': 'дисп'})
        self.assertContains(resp, 'Замена дисплея')
        self.assertNotContains(resp, 'Чистка ноутбука')

    def test_filter_by_device(self):
        resp = self.client.get(reverse('catalog:index'), {'device': self.laptop.pk})
        self.assertEqual([g.name for g in resp.context['groups']], ['Ноутбук'])

    def test_bad_device_param_ignored(self):
        resp = self.client.get(reverse('catalog:index'), {'device': 'abc'})
        self.assertEqual(len(resp.context['groups']), 2)

    def test_empty_result(self):
        self.assertContains(self.client.get(reverse('catalog:index'), {'q': 'нет-такого'}), 'Ничего не найдено')
