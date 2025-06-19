import datetime
from collections import defaultdict
from datetime import date, timedelta

from django.shortcuts import render, get_object_or_404
from django.http import Http404
from saints.models import CalendarEvent, Biography


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
            "date_link": day.strftime('%Y-%m-%d'),  # Add date string for linking
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


def daily_view(request, date):
    """Display calendar events for a specific date across different calendars."""
    try:
        # Parse the date string (expected format: YYYY-MM-DD)
        year, month, day = map(int, date.split('-'))
        target_date = datetime.date(year, month, day)
        
        # Validate date range (reasonable liturgical calendar range)
        if year < 1900 or year > 2100:
            raise Http404("Date out of range")
            
    except (ValueError, TypeError):
        raise Http404("Invalid date format")
    
    # Handle calendar switching via POST
    if request.method == 'POST':
        selected_calendar = request.POST.get('selected_calendar')
        if selected_calendar in ['catholic_1954', 'catholic_1962', 'current', 'ordinariate', 'acna', 'tec']:
            request.session['selected_calendar'] = selected_calendar
    
    # Get selected calendar from session, default to Catholic (Current)
    selected_calendar = request.session.get('selected_calendar', 'current')
    
    # Define calendar mappings
    calendar_options = {
        'catholic_1954': 'Catholic (1954)',
        'catholic_1962': 'Catholic (1962)', 
        'current': 'Catholic (Current)',
        'ordinariate': 'Catholic (Anglican Ordinariate)',
        'acna': 'ACNA (2019)',
        'tec': 'TEC (2024)'
    }
    
    # Filter mapping for database queries
    calendar_filters = {
        'catholic_1954': {'calendar__icontains': '1954'},
        'catholic_1962': {'calendar__icontains': '1960'},  # Note: 1962 uses 1960 in the code
        'current': {'calendar__icontains': 'catholic'},
        'ordinariate': {'calendar__icontains': 'ordinariate'},
        'acna': {'calendar__icontains': 'acna'},
        'tec': {'calendar__icontains': 'tec'}
    }
    
    # Get events for this date
    events = CalendarEvent.objects.filter(
        date=target_date,
        **calendar_filters.get(selected_calendar, calendar_filters['current'])
    ).order_by('order', 'english_name')
    
    # Try to find biography information for each event
    events_with_biographies = []
    for event in events:
        # Try to find a matching biography
        biography = None
        if event.saint_name:
            biography = Biography.objects.filter(name__icontains=event.saint_name).first()
        elif event.english_name and event.is_person:
            # Try exact match first, then partial match for saints/people
            biography = Biography.objects.filter(name__iexact=event.english_name).first()
            if not biography:
                # Extract first name part for more flexible matching
                name_part = event.english_name.split(',')[0].strip()
                biography = Biography.objects.filter(name__icontains=name_part).first()
        
        events_with_biographies.append({
            'event': event,
            'biography': biography
        })
    
    # Get navigation dates
    prev_date = target_date - timedelta(days=1)
    next_date = target_date + timedelta(days=1)
    
    context = {
        'date': target_date,
        'events': events,
        'events_with_biographies': events_with_biographies,
        'selected_calendar': selected_calendar,
        'calendar_options': calendar_options,
        'prev_date': prev_date,
        'next_date': next_date,
    }
    
    return render(request, "saints/daily.html", context)
