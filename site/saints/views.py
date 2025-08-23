import calendar
import datetime
from collections import defaultdict
import re
from datetime import date, timedelta

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from feedgen.feed import FeedGenerator
from saints.models import CalendarEvent, Podcast


def first_sunday_of_advent(year):
    """Return the date of the First Sunday of Advent for the given year."""
    christmas = datetime.date(year, 12, 25)
    weekday = christmas.weekday()  # Monday=0 ... Sunday=6
    days_to_sunday = (weekday + 1) % 7
    fourth_sunday_before = christmas - datetime.timedelta(days=days_to_sunday + 21)
    return fourth_sunday_before


def has_advent_started(today=None):
    """
    Return True if Advent has started as of `today` in the given `year`.
    If `today` is not provided, use the current date.
    """
    if today is None:
        today = datetime.date.today()
    advent_start = first_sunday_of_advent(today.year)
    return today >= advent_start


def home_view(request):
    """Redirect to today's daily view."""
    today = timezone.now().date()
    return redirect("daily_view", date=today.strftime("%Y-%m-%d"))


def comparison_view(request, year=None):
    def serialize_events(events):
        return [
            {
                "name": event.english_name,
                "rank": event.english_rank,
            }
            for event in events
        ]

    def format_display(events):
        rows = []
        for i, e in enumerate(events):
            if i == 0:
                rows.append(f"<strong>{e['name']}</strong> <small>({e['rank']})</small>")
            else:
                rows.append(f"{e['name']} <small>({e['rank']})</small>")
        return "<br>".join(rows)

    def group_events(events_queryset):
        grouped = defaultdict(list)
        for event in events_queryset:
            grouped[(event.month, event.day)].append(event)
        return grouped

    # Get the target day for scrolling (if provided)
    target_day = request.GET.get("day")

    # If target_day is provided, determine the correct liturgical year for that date
    if target_day:
        try:
            target_date = datetime.datetime.strptime(target_day, "%Y-%m-%d").date()
            # Determine the liturgical year for the target date
            if has_advent_started(target_date):
                target_liturgical_year = target_date.year
            else:
                target_liturgical_year = target_date.year - 1

            # If the target liturgical year is different from the requested year, redirect
            if year is None or int(year.split("-")[0]) != target_liturgical_year:
                url = reverse("comparison_with_year", kwargs={"year": target_liturgical_year})
                url += f"?day={target_day}"
                return HttpResponseRedirect(url)
        except (ValueError, TypeError):
            # If target_day is invalid, ignore it
            target_day = None

    if year is None:
        year = date.today().year
        if not has_advent_started():
            year -= 1
    else:
        year = int(year.split("-")[0])
    advent_1 = first_sunday_of_advent(year)
    advent_2 = first_sunday_of_advent(year + 1) - timedelta(days=1)

    # Fetch and group all calendar events by (month, day)
    base_filter = {"date__range": [advent_1, advent_2]}
    calendars = {
        "calendar_1954": group_events(CalendarEvent.objects.filter(**base_filter, calendar__icontains="1954")),
        "calendar_1960": group_events(CalendarEvent.objects.filter(**base_filter, calendar__icontains="1960")),
        "calendar_current": group_events(CalendarEvent.objects.filter(**base_filter, calendar__icontains="catholic")),
        "calendar_ordinariate": group_events(
            CalendarEvent.objects.filter(**base_filter, calendar__icontains="ordinariate")
        ),
        "calendar_acna": group_events(CalendarEvent.objects.filter(**base_filter, calendar__icontains="acna")),
        "calendar_tec": group_events(CalendarEvent.objects.filter(**base_filter, calendar__icontains="tec")),
    }

    # Build rows as list-of-dictionaries for Tabulator
    start_date = advent_1
    end_date = advent_2
    rows = []

    for i in range((end_date - start_date).days + 1):
        day = start_date + timedelta(days=i)
        month_day = (day.month, day.day)

        row = {
            "date": f"{day.strftime('%a')}<br><span style='font-size:1.1em;'><strong>{day.strftime('%b')} {day.strftime('%-d')}</strong><br>{day.strftime('%Y')}</span>",
            "date_link": day.strftime("%Y-%m-%d"),  # Add date string for linking
            "catholic_1954": format_display(serialize_events(calendars["calendar_1954"].get(month_day, []))),
            "catholic_1962": format_display(serialize_events(calendars["calendar_1960"].get(month_day, []))),
            "current": format_display(serialize_events(calendars["calendar_current"].get(month_day, []))),
            "ordinariate": format_display(serialize_events(calendars["calendar_ordinariate"].get(month_day, []))),
            "acna": format_display(serialize_events(calendars["calendar_acna"].get(month_day, []))),
            "tec": format_display(serialize_events(calendars["calendar_tec"].get(month_day, []))),
        }

        rows.append(row)

    today = date.today()

    # Calculate current liturgical year
    if has_advent_started(today):
        current_liturgical_year = today.year
    else:
        current_liturgical_year = today.year - 1

    return render(
        request,
        "saints/welcome.html",
        {
            "rows": rows,
            "year": year,
            "target_day": target_day,
            "today": today,
            "current_liturgical_year": current_liturgical_year,
        },
    )


def daily_view(request, date):
    """Display calendar events for a specific date across different calendars."""
    try:
        # Parse the date string (expected format: YYYY-MM-DD)
        year, month, day = map(int, date.split("-"))
        target_date = datetime.date(year, month, day)

        # Validate date range (reasonable liturgical calendar range)
        if year < 1900 or year > 2100:
            raise Http404("Date out of range")

    except (ValueError, TypeError):
        raise Http404("Invalid date format")

    # Handle calendar switching via POST
    if request.method == "POST":
        selected_calendar = request.POST.get("selected_calendar")
        if selected_calendar in ["catholic_1954", "catholic_1962", "current", "ordinariate", "acna", "tec"]:
            request.session["selected_calendar"] = selected_calendar

    # Get selected calendar from session or query parameter, default to Catholic (Current)
    selected_calendar = request.GET.get("calendar", request.session.get("selected_calendar", "current"))
    if selected_calendar in ["catholic_1954", "catholic_1962", "current", "ordinariate", "acna", "tec"]:
        request.session["selected_calendar"] = selected_calendar

    # Define calendar mappings
    calendar_options = {
        "catholic_1954": "Catholic (1954)",
        "catholic_1962": "Catholic (1962)",
        "current": "Catholic (Current)",
        "ordinariate": "Catholic (Anglican Ordinariate)",
        "acna": "ACNA (2019)",
        "tec": "TEC (2024)",
    }

    # Filter mapping for database queries
    calendar_filters = {
        "catholic_1954": {"calendar__icontains": "1954"},
        "catholic_1962": {"calendar__icontains": "1960"},  # Note: 1962 uses 1960 in the code
        "current": {"calendar__icontains": "catholic"},
        "ordinariate": {"calendar__icontains": "ordinariate"},
        "acna": {"calendar__icontains": "acna"},
        "tec": {"calendar__icontains": "tec"},
    }

    # Get events for this date
    events = CalendarEvent.objects.filter(
        date=target_date, **calendar_filters.get(selected_calendar, calendar_filters["current"])
    ).order_by("order", "english_name")

    # Gather a short preview of events on each calendar for this date
    calendar_peeks = {}
    for key in calendar_options:
        qs = CalendarEvent.objects.filter(date=target_date, **calendar_filters[key]).order_by("order", "english_name")
        preview_list = []
        for event in qs:
            if event.english_rank:
                preview_list.append(f"{event.english_name} ({event.english_rank})")
            else:
                preview_list.append(event.english_name)
        calendar_peeks[key] = "; ".join(preview_list)

    # Try to find biography information for each event
    events_with_biographies = []
    for event in events:
        # Only use direct foreign key relationship to biography
        biography = event.biography if event.biography else None

        events_with_biographies.append({"event": event, "biography": biography})

    # Get navigation dates
    prev_date = target_date - timedelta(days=1)
    next_date = target_date + timedelta(days=1)

    # Calculate current liturgical year
    today = timezone.now().date()
    if has_advent_started(today):
        current_liturgical_year = today.year
    else:
        current_liturgical_year = today.year - 1

    context = {
        "date": target_date,
        "events": events,
        "events_with_biographies": events_with_biographies,
        "selected_calendar": selected_calendar,
        "calendar_options": calendar_options,
        "calendar_peeks": calendar_peeks,
        "prev_date": prev_date,
        "next_date": next_date,
        "current_liturgical_year": current_liturgical_year,
    }

    return render(request, "saints/daily.html", context)


def calendar_view(request, year=None, month=None):
    """Display a monthly calendar view with liturgical events."""

    # Get current date if year/month not provided
    if not year or not month:
        today = timezone.now().date()
        year = year or today.year
        month = month or today.month
    else:
        year = int(year)
        month = int(month)

    # Validate year and month
    if year < 1900 or year > 2100 or month < 1 or month > 12:
        raise Http404("Invalid date")

    # Handle calendar switching via POST
    if request.method == "POST":
        selected_calendar = request.POST.get("selected_calendar")
        if selected_calendar in ["catholic_1954", "catholic_1962", "current", "ordinariate", "acna", "tec"]:
            request.session["selected_calendar"] = selected_calendar

    # Get selected calendar from session or query parameter, default to Catholic (Current)
    selected_calendar = request.GET.get("calendar", request.session.get("selected_calendar", "current"))
    if selected_calendar in ["catholic_1954", "catholic_1962", "current", "ordinariate", "acna", "tec"]:
        request.session["selected_calendar"] = selected_calendar

    # Define calendar mappings
    calendar_options = {
        "catholic_1954": "Catholic (1954)",
        "catholic_1962": "Catholic (1962)",
        "current": "Catholic (Current)",
        "ordinariate": "Catholic (Anglican Ordinariate)",
        "acna": "ACNA (2019)",
        "tec": "TEC (2024)",
    }

    # Filter mapping for database queries
    calendar_filters = {
        "catholic_1954": {"calendar__icontains": "1954"},
        "catholic_1962": {"calendar__icontains": "1960"},
        "current": {"calendar__icontains": "catholic"},
        "ordinariate": {"calendar__icontains": "ordinariate"},
        "acna": {"calendar__icontains": "acna"},
        "tec": {"calendar__icontains": "tec"},
    }

    # Get the calendar for the month (Sunday first)
    calendar.setfirstweekday(calendar.SUNDAY)
    cal = calendar.monthcalendar(year, month)

    # Get all events for this month
    events_this_month = CalendarEvent.objects.filter(
        date__year=year, date__month=month, **calendar_filters.get(selected_calendar, calendar_filters["current"])
    ).order_by("date", "order", "english_name")

    # Group events by day
    events_by_day = {}
    for event in events_this_month:
        day = event.date.day
        if day not in events_by_day:
            events_by_day[day] = []
        events_by_day[day].append(event)

    # Navigation dates
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    # Current date for highlighting
    today = timezone.now().date()

    # Calculate current liturgical year
    if has_advent_started(today):
        current_liturgical_year = today.year
    else:
        current_liturgical_year = today.year - 1

    context = {
        "year": year,
        "month": month,
        "month_name": calendar.month_name[month],
        "calendar_weeks": cal,
        "events_by_day": events_by_day,
        "selected_calendar": selected_calendar,
        "calendar_options": calendar_options,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
        "today": today,
        "current_liturgical_year": current_liturgical_year,
    }

    return render(request, "saints/calendar.html", context)


def podcast_feed(request, slug):
    """Return RSS feed for the given podcast (Apple Podcasts compatible)."""
    podcast = get_object_or_404(Podcast, slug=slug)

    # Remove characters not allowed by XML 1.0 (except tab, newline, carriage return)
    # This prevents lxml from raising ValueError when building CDATA/text nodes.
    def xml_safe(value):
        if value is None:
            return ""
        if not isinstance(value, str):
            value = str(value)
        return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", value)

    fg = FeedGenerator()
    fg.load_extension("podcast")
    fg.title(xml_safe(podcast.title))
    fg.link(href=podcast.link, rel="alternate")
    fg.language("en-us")
    fg.description(xml_safe(podcast.description or podcast.title))

    # Apple Podcasts/iTunes fields
    fg.podcast.itunes_author(xml_safe(getattr(settings, "PODCAST_AUTHOR", "Saints and Seasons")))
    fg.podcast.itunes_summary(xml_safe(podcast.description or podcast.title))
    fg.podcast.itunes_owner(
        xml_safe(getattr(settings, "PODCAST_OWNER_NAME", "Saints and Seasons")),
        xml_safe(getattr(settings, "PODCAST_OWNER_EMAIL", "ben@benlocher.com")),
    )
    fg.podcast.itunes_category("Religion & Spirituality", "Christianity")
    if podcast.image:
        fg.podcast.itunes_image(request.build_absolute_uri(podcast.image.url))
    fg.podcast.itunes_explicit("no")

    for episode in podcast.episodes.order_by("-date"):
        fe = fg.add_entry()
        fe.id(xml_safe(episode.slug))
        fe.title(xml_safe(episode.episode_title))
        fe.description(xml_safe(episode.episode_short_description))
        fe.pubDate(episode.published_date or episode.created)
        episode_url = request.build_absolute_uri(settings.MEDIA_URL + 'podcasts/' + episode.file_name)
        fe.link(href=episode_url)
        fe.guid(xml_safe(episode.slug), permalink=False)
        fe.enclosure(episode_url, 0, "audio/mpeg")
        # iTunes episode fields
        fe.podcast.itunes_title(xml_safe(episode.episode_title))
        fe.podcast.itunes_subtitle(xml_safe(getattr(episode, "episode_subtitle", "")))
        fe.podcast.itunes_summary(xml_safe(episode.episode_short_description))
        fe.podcast.itunes_explicit("no")
        fe.podcast.itunes_episode(getattr(episode, "episode_number", None))
        fe.podcast.itunes_duration(str(episode.duration) if getattr(episode, "duration", None) else "")
        # Add <content:encoded> for long description if available
        if getattr(episode, "episode_long_description", None):
            fe.content(xml_safe(episode.episode_long_description), type="CDATA")

    rss = fg.rss_str(pretty=True)
    return HttpResponse(rss, content_type="application/rss+xml")
