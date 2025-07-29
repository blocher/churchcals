from django.core.management.base import BaseCommand
from saints.podcasts import generate_next_day_podcast


class Command(BaseCommand):
    help = "Generate a podcast episode for tomorrow and set it to publish today at 5 PM"

    def handle(self, *args, **options):
        self.stdout.write("🎙️ Starting podcast generation for tomorrow...")
        
        try:
            result = generate_next_day_podcast()
            
            if result is None:
                self.stdout.write(
                    self.style.WARNING("⚠️ Podcast for tomorrow already exists, skipping generation")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Successfully generated podcast: {result}")
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Failed to generate podcast: {e}")
            )
            raise 