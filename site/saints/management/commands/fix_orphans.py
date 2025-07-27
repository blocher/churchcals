from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import transaction
from saints.models import Biography

class Command(BaseCommand):
    help = "Deletes any rows with orphaned biography_id foreign keys."

    def handle(self, *args, **options):
        biography_uuids = set(Biography.objects.values_list('uuid', flat=True))
        total_deleted = 0

        for model in apps.get_models():
            if not hasattr(model, '_meta'):
                continue

            fields = {f.name: f for f in model._meta.fields}

            if 'biography' not in fields:
                continue

            field = fields['biography']
            if not getattr(field, 'remote_field', None):
                continue

            if getattr(field.remote_field.model, '__name__', '') != 'Biography':
                continue

            self.stdout.write(f"\n🔍 Checking model: {model.__name__}")

            # Exclude rows with null biography_id
            qs = model.objects.exclude(biography__isnull=True)
            orphaned = qs.exclude(biography_id__in=biography_uuids)

            count = orphaned.count()
            if count > 0:
                with transaction.atomic():
                    orphaned.delete()
                self.stdout.write(f"❌ Deleted {count} orphaned rows from {model.__name__}")
                total_deleted += count
            else:
                self.stdout.write(f"✅ No orphaned rows in {model.__name__}")

        self.stdout.write(f"\n🧹 Cleanup complete. Total rows deleted: {total_deleted}")
