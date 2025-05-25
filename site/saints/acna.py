import json

import requests
from saints.current import enhance
from saints.models import CalendarEvent


def fetch_commemorations(calendar):
    commemorations = []
    session = requests.Session()

    for year in range(2020, 2036):
        for month in range(1, 13):
            url = f"https://api.dailyoffice2019.com/api/v1/calendar/{year}-{month}?calendar={calendar}"
            print(url)
            try:
                response = session.get(url)
                response.raise_for_status()
                days = response.json()

                for day in days:
                    date = day.get("date")
                    season = day.get("season", {}).get("name", "")
                    for i, commem in enumerate(day.get("commemorations", [])):
                        commemoration = {
                            "date": date,
                            "name": commem.get("name", ""),
                            "rank": commem.get("rank", {}).get("formatted_name", ""),
                            "color": commem.get("colors", [])[0] if commem.get("colors") else "",
                            "season": season,
                            "order": i,
                        }
                        commemorations.append(commemoration)
            except Exception as e:
                print(f"Failed for {url}: {e}")

    return commemorations


def run():
    calendars = [
        "TEC_BCP1979_LFF2024",
        "ACNA_BCP2019",
    ]
    for calendar in calendars:
        result = fetch_commemorations(calendar)
        for entry in result:
            if entry["name"] in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]:
                continue
            print(entry)
            year, month, day = entry["date"].split("-")
            event = CalendarEvent.objects.get_or_create(
                year=year, month=month, day=day, english_name=entry["name"], calendar=calendar
            )[0]

            event.english_rank = entry["rank"]
            event.color = entry["color"]
            event.season = entry["season"]
            event.order = entry["order"]

            enhancement = enhance(entry["name"])
            event.is_person = enhancement["is_person"]
            event.saint_name = enhancement["saint_name"]
            event.saint_category = enhancement["saint_category"]
            event.saint_categories = json.dumps(enhancement["saint_categories"])
            event.saint_singular_or_plural = enhancement["saint_singular_or_plural"]

            event.save()
