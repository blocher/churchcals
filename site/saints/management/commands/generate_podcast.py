from django.core.management.base import BaseCommand
from saints.podcasts import generate_next_day_podcast as generate_next_day_podcast_saints_and_seasons
from saints.kidspodcasts import generate_next_day_podcast as generate_next_day_podcast_saintly_adventures


class Command(BaseCommand):
    help = "Generate a podcast episode for tomorrow and set it to publish today at 5 PM"

    def _run_generator(self, label, func):
        try:
            result = func()
            if result is None:
                self.stdout.write(
                    self.style.WARNING(f"⚠️ {label}: Podcast for tomorrow already exists, skipping generation")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"✅ {label}: Successfully generated podcast: {result}")
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ {label}: Failed to generate podcast: {e}")
            )
            raise

    def handle(self, *args, **options):
        self.stdout.write("🎙️ Starting podcast generation for tomorrow...")
        generators = [
            ("Saints and Seasons", generate_next_day_podcast_saints_and_seasons),
            ("Saintly Adventures", generate_next_day_podcast_saintly_adventures),
        ]
        for label, func in generators:
            self._run_generator(label, func)