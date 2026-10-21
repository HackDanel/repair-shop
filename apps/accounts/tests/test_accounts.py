from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User

from .factories import PASSWORD, make_user


class RegistrationTests(TestCase):
    url = reverse('accounts:register')

    def data(self, **over):
        data = {
            'username': 'ivan', 'first_name': 'Иван', 'last_name': 'Петров', 'email': 'Ivan@Mail.ru',
            'phone': '+79131234567', 'password1': PASSWORD, 'password2': PASSWORD,
        }
        data.update(over)
        return data

    def test_register_creates_client_and_logs_in(self):
        resp = self.client.post(self.url, self.data())
        self.assertRedirects(resp, reverse('repairs:create'))
        user = User.objects.get(username='ivan')
        self.assertEqual(user.role, User.Role.CLIENT)
        self.assertEqual(user.email, 'ivan@mail.ru')
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_password_is_hashed(self):
        self.client.post(self.url, self.data())
        user = User.objects.get(username='ivan')
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.password.startswith('pbkdf2_sha256$'))
        self.assertTrue(user.check_password(PASSWORD))

    def test_cannot_register_as_admin_via_extra_field(self):
        self.client.post(self.url, self.data(role='admin'))
        self.assertEqual(User.objects.get(username='ivan').role, User.Role.CLIENT)

    def test_duplicate_email_rejected_case_insensitive(self):
        User.objects.create_user('other', email='ivan@mail.ru', password=PASSWORD)
        resp = self.client.post(self.url, self.data(email='IVAN@mail.ru'))
        self.assertEqual(resp.status_code, 200)
        self.assertFormError(resp.context['form'], 'email', 'Пользователь с таким e-mail уже зарегистрирован.')

    def test_weak_and_mismatched_passwords_rejected(self):
        for p1, p2 in [('1234567', '1234567'), ('12345678', '12345678'), (PASSWORD, PASSWORD + 'x')]:
            resp = self.client.post(self.url, self.data(password1=p1, password2=p2))
            self.assertEqual(resp.status_code, 200, (p1, p2))
        self.assertFalse(User.objects.filter(username='ivan').exists())

    def test_phone_validation_boundaries(self):
        # 9 цифр — мало, 10 и 15 — норма, 16 — много, буквы — нельзя.
        cases = {'123456789': False, '1234567890': True, '+123456789012345': True,
                 '1234567890123456': False, '+7913abc4567': False}
        for i, (phone, ok) in enumerate(cases.items()):
            resp = self.client.post(self.url, self.data(username=f'u{i}', email=f'u{i}@t.ru', phone=phone))
            self.assertEqual(User.objects.filter(username=f'u{i}').exists(), ok, phone)
            if ok:
                self.client.logout()
            else:
                self.assertIn('phone', resp.context['form'].errors)

    def test_required_fields(self):
        resp = self.client.post(self.url, {})
        errors = resp.context['form'].errors
        for field in ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']:
            self.assertIn(field, errors)


class LoginAndHomeTests(TestCase):
    def test_home_redirects_by_role(self):
        expected = {
            User.Role.CLIENT: 'repairs:my_list',
            User.Role.MASTER: 'repairs:master_list',
            User.Role.ADMIN: 'dashboard:requests',
        }
        for role, target in expected.items():
            user = make_user(f'user_{role}', role=role)
            self.client.force_login(user)
            self.assertRedirects(self.client.get(reverse('accounts:home')), reverse(target),
                                 fetch_redirect_response=False)

    def test_login_wrong_password(self):
        make_user('petr')
        resp = self.client.post(reverse('accounts:login'), {'username': 'petr', 'password': 'wrong'})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_inactive_user_cannot_login(self):
        make_user('blocked', is_active=False)
        self.client.post(reverse('accounts:login'), {'username': 'blocked', 'password': PASSWORD})
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_requires_post(self):
        self.client.force_login(make_user('petr'))
        self.assertEqual(self.client.get(reverse('accounts:logout')).status_code, 405)
        self.client.post(reverse('accounts:logout'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_superuser_is_admin_role(self):
        user = make_user('root', role=User.Role.CLIENT, is_superuser=True)
        self.assertTrue(user.is_admin_role)
