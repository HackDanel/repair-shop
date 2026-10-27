import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.accounts.models import User
from apps.accounts.tests.factories import make_catalog, make_user
from apps.repairs.models import RepairRequest, Status

MEDIA = tempfile.mkdtemp()


def image_file(name='photo.jpg', size=(40, 40), fmt='JPEG'):
    buf = io.BytesIO()
    Image.new('RGB', size, 'red').save(buf, fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT=MEDIA)
class CreateRequestTests(TestCase):
    url = reverse('repairs:create')

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.phone, self.laptop, self.screen = make_catalog()
        self.client_user = make_user('client')
        self.client.force_login(self.client_user)

    def data(self, **over):
        data = {'device_type': self.phone.pk, 'device_model': 'iPhone 13', 'serial_number': '',
                'service': '', 'problem': 'Разбит экран после падения'}
        data.update(over)
        return data

    def test_create_minimal(self):
        resp = self.client.post(self.url, self.data())
        req = RepairRequest.objects.get()
        self.assertRedirects(resp, reverse('repairs:detail', args=[req.pk]))
        self.assertEqual(req.client, self.client_user)
        self.assertEqual(req.status, Status.ACCEPTED)
        self.assertIsNone(req.master)
        self.assertEqual(req.status_changes.count(), 1)

    def test_create_with_photos(self):
        self.client.post(self.url, self.data(photos=[image_file('a.jpg'), image_file('b.png', fmt='PNG')]))
        self.assertEqual(RepairRequest.objects.get().photos.count(), 2)

    def test_problem_length_boundaries(self):
        for text, ok in [('x' * 9, False), ('x' * 10, True), ('x' * 2000, True), ('x' * 2001, False),
                         ('          ', False)]:
            RepairRequest.objects.all().delete()
            self.client.post(self.url, self.data(problem=text))
            self.assertEqual(RepairRequest.objects.exists(), ok, len(text))

    def test_service_must_match_device_type(self):
        resp = self.client.post(self.url, self.data(device_type=self.laptop.pk, service=self.screen.pk))
        self.assertIn('service', resp.context['form'].errors)
        self.assertFalse(RepairRequest.objects.exists())

    def test_too_many_photos(self):
        resp = self.client.post(self.url, self.data(photos=[image_file(f'{i}.jpg') for i in range(6)]))
        self.assertIn('photos', resp.context['form'].errors)

    def test_five_photos_is_ok(self):
        self.client.post(self.url, self.data(photos=[image_file(f'{i}.jpg') for i in range(5)]))
        self.assertEqual(RepairRequest.objects.get().photos.count(), 5)

    @override_settings(MAX_PHOTO_SIZE=1024)
    def test_photo_too_big(self):
        resp = self.client.post(self.url, self.data(photos=[image_file(size=(400, 400))]))
        self.assertIn('photos', resp.context['form'].errors)

    def test_non_image_rejected(self):
        fake = SimpleUploadedFile('virus.jpg', b'MZ\x90\x00not an image', content_type='image/jpeg')
        resp = self.client.post(self.url, self.data(photos=[fake]))
        self.assertIn('photos', resp.context['form'].errors)
        self.assertFalse(RepairRequest.objects.exists())

    def test_only_jpeg_png_webp_accepted(self):
        for fmt, ok in [('TIFF', False), ('BMP', False), ('GIF', False), ('WEBP', True)]:
            RepairRequest.objects.all().delete()
            self.client.post(self.url, self.data(photos=[image_file(f'p.{fmt.lower()}', fmt=fmt)]))
            self.assertEqual(RepairRequest.objects.exists(), ok, fmt)

    def test_prefill_from_catalog(self):
        resp = self.client.get(self.url, {'service': self.screen.pk})
        form = resp.context['form']
        self.assertEqual(form.initial['service'], self.screen)
        self.assertEqual(form.initial['device_type'], self.phone)

    def test_only_clients_can_create(self):
        self.client.force_login(make_user('m', role=User.Role.MASTER))
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_anonymous_redirected_to_login(self):
        self.client.logout()
        resp = self.client.get(self.url)
        self.assertRedirects(resp, f'{reverse("accounts:login")}?next={self.url}')


@override_settings(MEDIA_ROOT=MEDIA)
class AccessTests(TestCase):
    def setUp(self):
        phone, _, _ = make_catalog()
        self.owner = make_user('owner')
        self.stranger = make_user('stranger')
        self.master = make_user('master', role=User.Role.MASTER)
        self.other_master = make_user('master2', role=User.Role.MASTER)
        self.admin = make_user('boss', role=User.Role.ADMIN)
        self.req = RepairRequest.objects.create(client=self.owner, device_type=phone, device_model='X',
                                                problem='Не включается вообще', master=self.master)
        self.req.photos.create(image=image_file())
        self.url = reverse('repairs:detail', args=[self.req.pk])

    def status_for(self, user, url=None):
        self.client.force_login(user)
        return self.client.get(url or self.url).status_code

    def test_detail_visibility(self):
        self.assertEqual(self.status_for(self.owner), 200)
        self.assertEqual(self.status_for(self.master), 200)
        self.assertEqual(self.status_for(self.admin), 200)
        self.assertEqual(self.status_for(self.stranger), 404)
        self.assertEqual(self.status_for(self.other_master), 404)

    def test_photo_protected(self):
        photo_url = reverse('repairs:photo', args=[self.req.pk, self.req.photos.get().pk])
        self.assertEqual(self.status_for(self.owner, photo_url), 200)
        self.assertEqual(self.status_for(self.stranger, photo_url), 404)

    def test_client_list_shows_only_own(self):
        phone = self.req.device_type
        RepairRequest.objects.create(client=self.stranger, device_type=phone, device_model='Чужой', problem='y' * 10)
        self.client.force_login(self.owner)
        resp = self.client.get(reverse('repairs:my_list'))
        self.assertEqual(list(resp.context['active']), [self.req])

    def test_master_list_shows_only_assigned(self):
        RepairRequest.objects.create(client=self.owner, device_type=self.req.device_type, device_model='Y',
                                     problem='y' * 10, master=self.other_master)
        self.client.force_login(self.master)
        resp = self.client.get(reverse('repairs:master_list'))
        self.assertEqual(list(resp.context['page']), [self.req])

    def test_client_does_not_see_internal_comments(self):
        self.req.comments.create(author=self.master, text='Публичный')
        self.req.comments.create(author=self.master, text='Секрет', is_internal=True)
        self.client.force_login(self.owner)
        texts = [c.text for c in self.client.get(self.url).context['comments']]
        self.assertEqual(texts, ['Публичный'])
        self.client.force_login(self.master)
        self.assertEqual(len(self.client.get(self.url).context['comments']), 2)

    def test_client_cannot_post_internal_comment(self):
        self.client.force_login(self.owner)
        self.client.post(reverse('repairs:add_comment', args=[self.req.pk]), {'text': 'Вопрос', 'is_internal': 'on'})
        self.assertFalse(self.req.comments.get().is_internal)

    def test_client_cannot_change_status(self):
        self.client.force_login(self.owner)
        self.client.post(reverse('repairs:change_status', args=[self.req.pk]), {'status': Status.READY})
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, Status.ACCEPTED)

    def test_track_page_public_without_personal_data(self):
        self.client.logout()
        resp = self.client.get(reverse('repairs:track', args=[self.req.tracking_code]))
        self.assertContains(resp, 'Принята')
        self.assertNotContains(resp, self.owner.email)
        self.assertNotContains(resp, 'Не включается')

    def test_actions_require_post(self):
        self.client.force_login(self.master)
        resp = self.client.get(reverse('repairs:change_status', args=[self.req.pk]))
        self.assertEqual(resp.status_code, 405)
