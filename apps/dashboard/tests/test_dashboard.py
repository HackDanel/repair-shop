from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.tests.factories import PASSWORD, make_catalog, make_part, make_user
from apps.catalog.models import Service
from apps.repairs import services
from apps.repairs.models import Status


class AdminAccessTests(TestCase):
    urls = ['dashboard:requests', 'dashboard:staff', 'dashboard:clients', 'dashboard:services',
            'dashboard:stats', 'dashboard:stats_json', 'dashboard:staff_create', 'dashboard:service_create']

    def test_only_admin(self):
        for role, code in [(User.Role.CLIENT, 403), (User.Role.MASTER, 403), (User.Role.ADMIN, 200)]:
            self.client.force_login(make_user(f'u_{role}', role=role))
            for name in self.urls:
                self.assertEqual(self.client.get(reverse(name)).status_code, code, (role, name))


class StaffTests(TestCase):
    def setUp(self):
        self.admin = make_user('boss', role=User.Role.ADMIN)
        self.client.force_login(self.admin)

    def test_create_master(self):
        self.client.post(reverse('dashboard:staff_create'), {
            'username': 'newmaster', 'first_name': 'А', 'last_name': 'Б', 'email': 'nm@t.ru',
            'phone': '', 'role': 'master', 'is_active': 'on', 'password': PASSWORD,
        })
        user = User.objects.get(username='newmaster')
        self.assertTrue(user.is_master)
        self.assertTrue(user.check_password(PASSWORD))

    def test_new_staff_requires_password(self):
        resp = self.client.post(reverse('dashboard:staff_create'), {
            'username': 'x', 'email': 'x@t.ru', 'role': 'master', 'is_active': 'on',
        })
        self.assertIn('password', resp.context['form'].errors)

    def test_edit_keeps_password_when_empty(self):
        master = make_user('m', role=User.Role.MASTER)
        old_hash = master.password
        self.client.post(reverse('dashboard:staff_edit', args=[master.pk]), {
            'username': 'm', 'email': 'm@test.local', 'role': 'master', 'is_active': 'on', 'password': '',
        })
        master.refresh_from_db()
        self.assertEqual(master.password, old_hash)

    def test_admin_cannot_lock_himself_out(self):
        resp = self.client.post(reverse('dashboard:staff_edit', args=[self.admin.pk]), {
            'username': 'boss', 'email': 'boss@test.local', 'role': 'master', 'password': '',
        })
        self.assertEqual(resp.status_code, 200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_admin_role and self.admin.is_active)

    def test_block_client(self):
        c = make_user('c')
        self.client.post(reverse('dashboard:toggle_active', args=[c.pk]))
        c.refresh_from_db()
        self.assertFalse(c.is_active)


class ServicesAndFiltersTests(TestCase):
    def setUp(self):
        self.phone, self.laptop, self.screen = make_catalog()
        self.admin = make_user('boss', role=User.Role.ADMIN)
        self.client.force_login(self.admin)

    def test_create_service_and_hide_from_catalog(self):
        self.client.post(reverse('dashboard:service_create'), {
            'device_type': self.laptop.pk, 'name': 'Чистка', 'price_from': '1500', 'duration_days': 1,
        })
        service = Service.objects.get(name='Чистка')
        self.assertFalse(service.is_active)  # чекбокс не отмечен — услуга скрыта
        groups = self.client.get(reverse('catalog:index')).context['groups']
        names = [s.name for g in groups for s in g.visible_services]
        self.assertEqual(names, ['Замена дисплея'])

    def test_service_price_and_duration_boundaries(self):
        url = reverse('dashboard:service_create')
        base = {'device_type': self.phone.pk, 'is_active': 'on'}
        for i, (price, days, ok) in enumerate([('0', 1, True), ('-0.01', 1, False), ('100', 0, False)]):
            self.client.post(url, {**base, 'name': f'S{i}', 'price_from': price, 'duration_days': days})
            self.assertEqual(Service.objects.filter(name=f'S{i}').exists(), ok, (price, days))

    def test_duplicate_device_type(self):
        self.client.post(reverse('dashboard:device_type_create'), {'name': 'смартфон'}, follow=True)
        self.assertEqual(self.phone.__class__.objects.filter(name__iexact='смартфон').count(), 1)

    def test_request_filters(self):
        owner = make_user('owner')
        master = make_user('m', role=User.Role.MASTER)
        a = services.create_request(owner, device_type=self.phone, device_model='iPhone', problem='y' * 10)
        b = services.create_request(owner, device_type=self.phone, device_model='Pixel', problem='y' * 10)
        services.assign_master(b, master, self.admin)
        url = reverse('dashboard:requests')
        self.assertEqual(list(self.client.get(url, {'master': 'none'}).context['page']), [a])
        self.assertEqual(list(self.client.get(url, {'master': master.pk}).context['page']), [b])
        self.assertEqual(list(self.client.get(url, {'q': 'pixel'}).context['page']), [b])
        self.assertEqual(list(self.client.get(url, {'q': str(a.pk)}).context['page']), [a])

    def test_search_with_sql_metacharacters_is_safe(self):
        for q in ["' OR 1=1 --", '"; DROP TABLE accounts_user; --', '%', '_']:
            self.assertEqual(self.client.get(reverse('dashboard:requests'), {'q': q}).status_code, 200)
            self.assertEqual(self.client.get(reverse('catalog:index'), {'q': q}).status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())


class StatsTests(TestCase):
    def test_revenue_counts_issued_labor_and_parts(self):
        phone, _, _ = make_catalog()
        admin = make_user('boss', role=User.Role.ADMIN)
        master = make_user('m', role=User.Role.MASTER)
        part = make_part(price='500', quantity=10)
        req = services.create_request(make_user('c'), device_type=phone, device_model='X', problem='y' * 10)
        services.assign_master(req, master, admin)
        services.set_labor_cost(req, Decimal('1000'), master)
        services.use_part(req, part.pk, 2, master)
        open_req = services.create_request(make_user('c2'), device_type=phone, device_model='Y', problem='y' * 10)
        services.set_labor_cost(open_req, Decimal('7777'), admin)
        for s in [Status.DIAGNOSTICS, Status.READY, Status.ISSUED]:
            services.change_status(req, s, master)

        self.client.force_login(admin)
        data = self.client.get(reverse('dashboard:stats_json')).json()
        self.assertEqual(data['charts']['revenue'][-1], 2000.0)  # незакрытая заявка не в доходе
        self.assertEqual(data['charts']['requests'][-1], 2)
        self.assertEqual(data['kpi']['active'], 1)
        self.assertEqual(data['kpi']['unassigned'], 1)
        self.assertEqual(len(data['charts']['months']), 12)
        self.assertEqual(data['charts']['masters'], {'labels': [str(master)], 'active': [0], 'done': [1]})
