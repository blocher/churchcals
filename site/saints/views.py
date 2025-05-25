import datetime
from collections import defaultdict
from datetime import date, timedelta

from django.shortcuts import render
from saints.models import CalendarEvent


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


def welcome_view(request, year=None):
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
            "catholic_1954": format_display(serialize_events(calendars["calendar_1954"].get(month_day, []))),
            "catholic_1962": format_display(serialize_events(calendars["calendar_1960"].get(month_day, []))),
            "current": format_display(serialize_events(calendars["calendar_current"].get(month_day, []))),
            "ordinariate": format_display(serialize_events(calendars["calendar_ordinariate"].get(month_day, []))),
            "acna": format_display(serialize_events(calendars["calendar_acna"].get(month_day, []))),
            "tec": format_display(serialize_events(calendars["calendar_tec"].get(month_day, []))),
        }

        rows.append(row)

    print(rows[:-1])

    return render(request, "saints/welcome.html", {"rows": rows, "year": year})
