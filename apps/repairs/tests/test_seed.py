from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from apps.inventory.models import Part
from apps.repairs.models import RepairRequest, Status


class SeedDemoTests(TestCase):
    def test_seed_creates_consistent_data_once(self):
        call_command('seed_demo', requests=30, stdout=StringIO())
        self.assertEqual(RepairRequest.objects.count(), 30)
        now = timezone.now()
        for req in RepairRequest.objects.all():
            self.assertEqual(req.status == Status.ISSUED, req.issued_at is not None)
            if req.issued_at:
                self.assertLessEqual(req.issued_at, now)
                self.assertGreaterEqual(req.issued_at, req.created_at)
        self.assertFalse(Part.objects.filter(quantity__lt=0).exists())
        with self.assertRaises(CommandError):
            call_command('seed_demo', stdout=StringIO())
