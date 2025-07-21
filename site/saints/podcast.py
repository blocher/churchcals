from datetime import date, timedelta

from django.utils import timezone
from django.utils.text import slugify

from .models import CalendarEvent, Podcast, PodcastEpisode


def create_full_podcast(target_date: date) -> PodcastEpisode:
    """Generate podcast metadata and create a PodcastEpisode object."""
    # gather saints for the current calendar
    events = CalendarEvent.objects.filter(date=target_date, calendar__icontains="catholic")
    saint_names = [e.english_name for e in events if e.english_name]
    episode_title = ", ".join(saint_names) if saint_names else target_date.strftime("Saints for %B %d")
    subtitle = f"Celebrations for {target_date.strftime('%B %d, %Y')}"
    base_link = f"https://saints.benlocher.com/day/{target_date.isoformat()}/?calendar=current"
    short_description = f"{base_link} - Daily saints."
    long_description = f"{base_link} - Learn more about today's commemorations on the site."
    full_text = "\n".join(f"{e.english_name} ({e.english_rank})" for e in events)

    podcast, _ = Podcast.objects.get_or_create(
        slug="saints-and-seasons",
        defaults={"title": "Saints and Seasons", "religion": "Catholic"},
    )

    slug = slugify(target_date.isoformat())
    episode = PodcastEpisode.objects.create(
        slug=slug,
        date=target_date,
        published_date=timezone.now(),
        podcast=podcast,
        file_name=f"{slug}.mp3",
        url=f"/media/podcasts/{slug}.mp3",
        episode_title=episode_title,
        episode_subtitle=subtitle,
        episode_short_description=short_description,
        episode_long_description=long_description,
        episode_full_text=full_text,
    )
    return episode
