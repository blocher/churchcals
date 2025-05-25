import json
import re
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup
from saints.current import enhance
from saints.models import CalendarEvent


def fetch_ordinariate_calendar(calendar, year):
    url = calendar[1] + str(year)
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    data = []

    # Mapping Universalis color classes to color names
    color_map = {
        "lit-w": "white",
        "lit-r": "red",
        "lit-g": "green",
        "lit-p": "purple",
        "lit-k": "rose",
        "lit-b": "black",
    }
    month_map = {
        "January": 1,
        "February": 2,
        "March": 3,
        "April": 4,
        "May": 5,
        "June": 6,
        "July": 7,
        "August": 8,
        "September": 9,
        "October": 10,
        "November": 11,
        "December": 12,
    }

    current_month = None
    current_year = year

    for row in soup.select("#yearly-calendar tr"):
        if row.find("th"):
            month_text = row.get_text(strip=True)
            if month_text in month_map:
                current_month = month_map[month_text]
            continue

        cols = row.find_all("td")
        if len(cols) < 2:
            continue

        date_cell = cols[0]
        content_cell = cols[1]

        date_link = date_cell.find("a", href=True)
        if date_link:
            try:
                date_str = date_link["href"].split("/")[-2]
                date = datetime.strptime(date_str, "%Y%m%d").date()
            except Exception:
                continue
        else:
            # fallback: extract date from text like "Wed 1" or "Fri 10"
            match = re.search(r"(\d{1,2})", date_cell.get_text())
            if match and current_month:
                try:
                    date = datetime(current_year, current_month, int(match.group(1))).date()
                except ValueError:
                    continue
            else:
                continue

        # Use actual <br> tags as separators
        content_parts = []
        for elem in content_cell.contents:
            if elem.name == "br":
                content_parts.append("<br>")
            else:
                content_parts.append(str(elem))

        segments = "".join(content_parts).split("<br>")

        order = -1
        for segment_html in segments:
            order += 1
            segment_soup = BeautifulSoup(segment_html, "html.parser")
            full_text = segment_soup.get_text(" ", strip=True)

            if not full_text:
                continue

            # Remove leading "or" and whitespace
            if full_text.lower().startswith("or "):
                full_text = full_text[3:].strip()

            # Determine liturgical color
            span = segment_soup.find("span", class_=lambda c: c and c.startswith("lit-"))
            color_class = span["class"][0] if span else None
            color = color_map.get(color_class, None)

            # Check for commemoration pattern
            if full_text.lower().startswith("(commemoration of") and full_text.endswith(")"):
                full_text = full_text[17:-1].strip()
                rank = "commemoration"
                if not color:
                    color = "red" if "martyr" in full_text.lower() else "white"
            else:
                # Determine rank
                rank = "feria_or_optional_memorial"
                if segment_soup.find("span", class_="rank-3"):
                    rank = "Solemnity"
                elif segment_soup.find("span", class_="rank-6"):
                    rank = "Sunday"
                elif segment_soup.find("span", class_="rank-7"):
                    rank = "Feast"
                elif segment_soup.find("span", class_="rank-10"):
                    rank = "Memorial"

                feria_names = [
                    "of advent",
                    "of christmas",
                    " december",
                    "after Trinity",
                    "Saturday memorial",
                    "after Pentecost",
                    "of Eastertide",
                    "before Ascension Sunday",
                    "of Lent",
                    "after Ash Wednesday",
                    " after ",
                    "after Epiphany",
                    " January",
                ]

                if rank == "feria_or_optional_memorial":
                    rank = "Optional Memorial"
                    for name in feria_names:
                        if name.lower() in full_text.lower():
                            rank = "Feria"
                            break

            data.append(
                {
                    "date": str(date),
                    "name": full_text,
                    "rank": rank,
                    "color": color,
                    "order": order,
                    "season": None,
                }
            )
            print(f"Date: {date}, Feast: {full_text}, Rank: {rank}, Color: {color}, Order: {order}")
    return data


def run():
    calendars = [
        ("ordinarate", "https://universalis.com/usa.ordinariate.thursday/calendar.htm?year="),
        ("catholic", "https://universalis.com/usa.thursday/calendar.htm?year="),
    ]
    for calendar in calendars:
        for year in range(2020, 2036):
            print(f"Fetching calendar for {calendar[0]} {year}")
            result = fetch_ordinariate_calendar(calendar, year)
            for entry in result:
                print(entry)
                year, month, day = entry["date"].split("-")
                print(year, month, day)
                event = CalendarEvent.objects.get_or_create(
                    year=int(year),
                    month=int(month),
                    day=int(day),
                    date=date(int(year), int(month), int(day)),
                    english_name=entry["name"],
                    calendar=calendar[0],
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
                print(event.pk, event)
                print(f"Enhancement: {enhancement}")
