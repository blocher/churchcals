from datetime import timedelta

from django.utils import timezone
from django_cron import CronJobBase, Schedule

from .podcast import create_full_podcast


class CreatePodcastCronJob(CronJobBase):
    """Cron job to create the daily podcast episode."""

    schedule = Schedule(run_at_times=["22:00"])  # roughly 5 PM ET
    code = "saints.create_podcast_cron"

    def do(self):
        target_date = timezone.now().date() + timedelta(days=1)
        create_full_podcast(target_date)
