import calendar
import datetime
from collections import defaultdict
import re
from datetime import date, timedelta
import os
import time
import hashlib
from typing import Iterator, Optional, Tuple

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseRedirect, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from feedgen.feed import FeedGenerator
from saints.models import CalendarEvent, Podcast, PodcastEpisode, PodcastListenLog
from django.core.files.storage import default_storage
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.dateparse import parse_date


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
        # Use streaming audio endpoint for enclosures
        episode_path = reverse("podcast-audio", kwargs={"podcast_slug": podcast.slug, "episode_slug": episode.slug})
        episode_url = request.build_absolute_uri(episode_path)
        fe.link(href=episode_url)
        fe.guid(xml_safe(episode.slug), permalink=False)
        # Best-effort file length determination for enclosure length
        try:
            rel_path = os.path.join("podcasts", episode.file_name)
            size = default_storage.size(rel_path)  # type: ignore[arg-type]
        except Exception:
            size = 0
        fe.enclosure(episode_url, size, "audio/mpeg")
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


def _get_client_ip(request) -> Tuple[Optional[str], Optional[str]]:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        # X-Forwarded-For may contain multiple IPs; the first is the original client
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        ip = parts[0] if parts else None
        return ip, xff
    return request.META.get("REMOTE_ADDR"), None


def _best_effort_geo(ip: Optional[str]):
    geo = {
        "geo_country": None,
        "geo_region": None,
        "geo_city": None,
        "geo_latitude": None,
        "geo_longitude": None,
    }
    if not ip:
        return geo
    try:
        from django.contrib.gis.geoip2 import GeoIP2  # type: ignore

        g = GeoIP2()
        city = g.city(ip)
        if city:
            geo.update(
                {
                    "geo_country": city.get("country_code"),
                    "geo_region": city.get("region"),
                    "geo_city": city.get("city"),
                    "geo_latitude": city.get("latitude"),
                    "geo_longitude": city.get("longitude"),
                }
            )
    except Exception:
        # GeoIP not configured or lookup failed
        pass
    return geo


def _humanize_bytes(num: Optional[int]) -> str:
    if not num or num < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(num)
    idx = 0
    while size >= 1000.0 and idx < len(units) - 1:
        size /= 1000.0
        idx += 1
    if idx == 0:
        return f"{int(size)} {units[idx]}"
    return f"{size:.2f} {units[idx]}"


def _file_iterator(path: str, start: int, length: int, chunk_size: int = 8192) -> Iterator[bytes]:
    with open(path, "rb") as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            read_len = min(chunk_size, remaining)
            data = f.read(read_len)
            if not data:
                break
            remaining -= len(data)
            yield data


def _resolve_storage_path(rel_path: str) -> Tuple[Optional[str], Optional[int]]:
    """Return a local filesystem path and size if available for the storage key."""
    try:
        # Prefer storage.path if available
        path = default_storage.path(rel_path)  # type: ignore[attr-defined]
        size = os.path.getsize(path)
        return path, size
    except Exception:
        # Fallback: try to open to compute size via storage API
        try:
            size = default_storage.size(rel_path)  # type: ignore[arg-type]
        except Exception:
            size = None
        return None, size


def _parse_range_header(range_header: str, total_size: int) -> Optional[Tuple[int, int]]:
    # Expected format: bytes=start-end
    if not range_header or not range_header.startswith("bytes="):
        return None
    try:
        ranges = range_header.split("=", 1)[1]
        start_str, end_str = ranges.split("-", 1)
        if start_str == "":
            # suffix range: last N bytes
            suffix = int(end_str)
            if suffix <= 0:
                return None
            start = max(0, total_size - suffix)
            end = total_size - 1
        else:
            start = int(start_str)
            end = int(end_str) if end_str else total_size - 1
        if start > end or start < 0 or end >= total_size:
            return None
        return start, end
    except Exception:
        return None


def _build_fingerprint(ip: Optional[str], ua: Optional[str], session_key: Optional[str]) -> str:
    base = f"{ip or ''}|{ua or ''}|{session_key or ''}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def serve_podcast_audio(request, podcast_slug: str, episode_slug: str):
    """Stream MP3 audio with HTTP Range support and listen logging."""
    podcast = get_object_or_404(Podcast, slug=podcast_slug)
    episode = get_object_or_404(PodcastEpisode, slug=episode_slug, podcast=podcast)

    rel_path = os.path.join("podcasts", episode.file_name)
    local_path, total_size = _resolve_storage_path(rel_path)
    if total_size is None:
        raise Http404("Audio file not found")

    mime_type = "audio/mpeg"
    range_header = request.META.get("HTTP_RANGE")
    status_code = 200
    start = 0
    end = total_size - 1
    is_partial = False
    if range_header:
        rng = _parse_range_header(range_header, total_size)
        if rng:
            start, end = rng
            status_code = 206
            is_partial = True

    length = end - start + 1

    # HEAD support
    if request.method == "HEAD":
        response = HttpResponse(status=status_code, content_type=mime_type)
        response["Accept-Ranges"] = "bytes"
        response["Content-Length"] = str(length)
        if is_partial:
            response["Content-Range"] = f"bytes {start}-{end}/{total_size}"
        response["Content-Disposition"] = f"inline; filename=\"{os.path.basename(episode.file_name)}\""
        return response

    # Build response
    if local_path:
        iterator = _file_iterator(local_path, start, length)
        response = StreamingHttpResponse(iterator, status=status_code, content_type=mime_type)
    else:
        # Storage without local path: read via storage
        f = default_storage.open(rel_path, "rb")  # type: ignore[arg-type]
        try:
            if start:
                f.seek(start)
        except Exception:
            pass

        def _stream() -> Iterator[bytes]:
            remaining = length
            while remaining > 0:
                chunk = f.read(min(8192, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

        response = StreamingHttpResponse(_stream(), status=status_code, content_type=mime_type)

    response["Accept-Ranges"] = "bytes"
    response["Content-Length"] = str(length)
    if is_partial:
        response["Content-Range"] = f"bytes {start}-{end}/{total_size}"
    response["Content-Disposition"] = f"inline; filename=\"{os.path.basename(episode.file_name)}\""

    # Logging with playback grouping
    t0 = time.time()
    client_ip, xff = _get_client_ip(request)
    geo = _best_effort_geo(client_ip)
    ua = request.META.get("HTTP_USER_AGENT")
    session_key = getattr(request, "session", None) and request.session.session_key
    fingerprint = _build_fingerprint(client_ip, ua, session_key)

    # Session-scoped playback grouping per episode
    if hasattr(request, "session"):
        session_playback_key = f"playback:{podcast.slug}:{episode.slug}"
        playback_info = request.session.get(session_playback_key)
        if not playback_info:
            playback_id = hashlib.sha256(f"{fingerprint}|{episode.slug}|{time.time()}".encode("utf-8")).hexdigest()[:32]
            request_index = 0
        else:
            playback_id = playback_info.get("id")
            request_index = int(playback_info.get("n", 0)) + 1
        request.session[session_playback_key] = {"id": playback_id, "n": request_index}
    else:
        playback_id = hashlib.sha256(f"{fingerprint}|{episode.slug}".encode("utf-8")).hexdigest()[:32]
        request_index = None

    is_seek = bool(is_partial and start > 0)

    log = PodcastListenLog.objects.create(
        podcast=podcast,
        episode=episode,
        method=request.method,
        path=request.get_full_path()[:2048],
        referrer=request.META.get("HTTP_REFERER", "")[:2048] or None,
        user_agent=ua,
        ip_address=client_ip,
        x_forwarded_for=xff,
        session_key=session_key,
        user=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
        range_header=range_header,
        range_start=start,
        range_end=end,
        total_size=total_size,
        bytes_served=length,
        is_partial=is_partial,
        status_code=status_code,
        fingerprint_sha256=fingerprint,
        playback_id=playback_id,
        is_seek=is_seek,
        request_index=request_index,
        **geo,
    )

    # Defer measuring response time; attach a close callback
    def _close():
        try:
            dt = int((time.time() - t0) * 1000)
            PodcastListenLog.objects.filter(pk=log.pk).update(response_time_ms=dt)
        except Exception:
            pass

    response.close = (lambda orig_close=response.close: (lambda: (orig_close(), _close())))()

    return response


@staff_member_required
def podcast_analytics_dashboard(request):
    """Admin-only dashboard with podcast listening metrics."""
    # Aggregate metrics
    from django.db.models import Count, Sum, Value, Func
    from django.db.models.functions import TruncDate, Coalesce, Concat
    from django.utils import timezone as _tz

    now = _tz.now()
    # Date range filters (inclusive). Defaults to last 30 days.
    start_param = request.GET.get("start")
    end_param = request.GET.get("end")
    start_date = parse_date(start_param) if start_param else None
    end_date = parse_date(end_param) if end_param else None
    if not end_date:
        end_date = now.date()
    if not start_date:
        start_date = end_date - datetime.timedelta(days=30)

    logs_qs = PodcastListenLog.objects.filter(created__date__gte=start_date, created__date__lte=end_date)
    # Build a consistent unique-listen key per requestor
    logs_qs = logs_qs.annotate(
        ukey=Coalesce(
            "fingerprint_sha256",
            "playback_id",
            Func(
                Concat("ip_address", Value("|"), "user_agent", Value("|"), "session_key"),
                function="md5",
            ),
        )
    )

    # Unique listens: distinct by (episode, fingerprint)
    total_listens = logs_qs.values("episode", "ukey").distinct().count()
    total_bytes = logs_qs.aggregate(b=Sum("bytes_served")).get("b") or 0
    total_bytes_human = _humanize_bytes(total_bytes)

    top_episodes = (
        logs_qs.values(
            "episode__uuid",
            "episode__episode_title",
            "episode__podcast__title",
        )
        .annotate(c=Count("ukey", distinct=True))
        .order_by("-c")[:10]
    )

    top_podcasts = (
        logs_qs.values("podcast__uuid", "podcast__title", "episode", "ukey")
        .distinct()
        .values("podcast__uuid", "podcast__title")
        .annotate(c=Count("podcast__uuid"))
        .order_by("-c")[:10]
    )

    # Unique listens per day: distinct (episode, fingerprint) per day
    raw_by_day = (
        logs_qs
        .annotate(day=TruncDate("created"))
        .values("day", "episode", "ukey")
        .distinct()
        .values("day")
        .annotate(c=Count("day"))
        .order_by("day")
    )
    # Fill all days in the selected range
    _day_counts = {row["day"]: row["c"] for row in raw_by_day}
    listens_by_day = []
    _d = start_date
    while _d <= end_date:
        listens_by_day.append({"day": _d, "c": _day_counts.get(_d, 0)})
        _d += datetime.timedelta(days=1)

    # Unique listens per country: distinct (episode, fingerprint) per country
    top_countries = (
        logs_qs.exclude(geo_country__isnull=True)
        .values("geo_country", "episode", "ukey")
        .distinct()
        .values("geo_country")
        .annotate(c=Count("geo_country"))
        .order_by("-c")[:10]
    )

    # Unique listens per user agent: distinct (episode, fingerprint) per UA
    top_user_agents = (
        logs_qs.exclude(user_agent__isnull=True)
        .values("user_agent", "episode", "ukey")
        .distinct()
        .values("user_agent")
        .annotate(c=Count("user_agent"))
        .order_by("-c")[:10]
    )

    context = {
        "total_listens": total_listens,
        "total_bytes": total_bytes,
        "total_bytes_human": total_bytes_human,
        "top_episodes": top_episodes,
        "top_podcasts": top_podcasts,
        "listens_by_day": listens_by_day,
        "top_countries": top_countries,
        "top_user_agents": top_user_agents,
        "start_date": start_date,
        "end_date": end_date,
    }
    return render(request, "saints/admin/analytics.html", context)
