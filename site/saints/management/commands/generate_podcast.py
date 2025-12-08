import datetime
from django.core.management.base import BaseCommand
from django.core.management import CommandError
from saints.podcasts import generate_next_day_podcast as generate_next_day_podcast_saints_and_seasons
from saints.kidspodcasts import generate_next_day_podcast as generate_next_day_podcast_saintly_adventures


class Command(BaseCommand):
    help = "Generate a podcast episode for tomorrow and set it to publish today at 5 PM"

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="date",
            help="Generate for a specific date (YYYY-MM-DD) instead of tomorrow",
            type=str,
            required=False,
        )

    def _run_generator(self, label, run_callable, target_date_str: str):
        try:
            result = run_callable()
            if result is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠️ {label}: Podcast for {target_date_str} already exists, skipping generation"
                    )
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
        date_str = options.get("date")
        date_override = None
        if date_str:
            try:
                date_override = datetime.date.fromisoformat(date_str)
            except ValueError:
                raise CommandError("Invalid --date format. Use YYYY-MM-DD.")

        target_label = date_str if date_override else "tomorrow"
        self.stdout.write(f"🎙️ Starting podcast generation for {target_label}...")

        generators = [
            (
                "Saints and Seasons",
                (lambda: generate_next_day_podcast_saints_and_seasons(date_override)),
            ),
            (
                "Saintly Adventures",
                (lambda: generate_next_day_podcast_saintly_adventures(date_override)),
            ),
        ]
        for label, callable_fn in generators:
            # Use the label-friendly date string for messages
            label_date_str = date_str if date_override else "tomorrow"
            self._run_generator(label, callable_fn, label_date_str)