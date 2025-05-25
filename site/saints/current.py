import json
import re
from datetime import date, datetime, timedelta
from pprint import pprint

import requests
from bs4 import BeautifulSoup, Tag
from deep_translator import ChatGptTranslator, GoogleTranslator
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from saints import settings
from saints.models import CalendarEvent


def parse_gcatholic_calendar(url):
    year = int(url.strip("/").split("/")[-2])  # Extract year from URL
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    table = soup.find("table", class_="tb")
    rows = table.find_all("tr")

    current_season = None
    current_date = None
    results = []
    month = 0
    day = 0
    order = 0
    for row in rows:
        if "tbhd" in row.get("class", []):
            continue

        tds = row.find_all("td")

        # Rule 3.1: single cell with season info
        if len(tds) == 1:
            season_div = row.find("div", class_="season")
            if season_div:
                current_season = season_div.get_text(strip=True)
            continue

        # Rule 4: id in MMDD format
        row_id = row.get("id")
        if row_id and len(row_id) == 4 and row_id.isdigit():
            month = int(row_id[:2])
            day = int(row_id[2:])
            current_date = datetime(year, month, day).date()
            order = 0

        # Rule 5: normalize to 2 cells

        if len(tds) == 5:
            tds = tds[2:-1]
        elif len(tds) == 4:
            tds = tds[2:]
        elif len(tds) != 2:
            continue  # skip if not 2, 4, or 5 tds

        rank_td, name_td = tds

        # Rule 6: rank determination
        a_tag = rank_td.find("a")
        if a_tag and "title" in a_tag.attrs:
            rank = a_tag["title"]
        else:
            if current_date and current_date.strftime("%A") == "Sunday":
                rank = "Sunday"
            else:
                rank = "Weekday"

        # Rule 7: color determination
        color = None
        span = name_td.find("span", class_="feastg")
        if span:
            color = "green"
        if not color and name_td.find("span", class_="feastw"):
            color = "white"
        if not color and name_td.find("span", class_="feastv"):
            color = "purple"
        if not color and name_td.find("span", class_="feastp"):
            color = "rose"
        if not color and name_td.find("span", class_="feastr"):
            color = "red"

        # Rule 8: name stripping HTML
        name = name_td.get_text(separator=" ", strip=True).replace(" ,", ",")
        if current_date:
            results.append(
                {
                    "year": current_date.year,
                    "month": current_date.month,
                    "day": current_date.day,
                    "season": current_season,
                    "rank": rank,
                    "color": color,
                    "name": name,
                    "order": order,
                }
            )

        order = order + 1

    return results


class FeastName(BaseModel):
    is_person: bool = Field(
        description="True if the feast is a saint or saints, False if it is something else (like commemorating an event or season)."
    )
    saint_name: str | None = Field(
        description="Just the name of the saint or saints in English, if applicable. If the feast is not a saint, this should be None. Do not include 'Saint', 'Saints', 'S.', 'Ss', etc."
    )
    saint_category: str | None = Field(
        description="The category of the saint or saints in English, if applicable. If the feast is not a saint, this should be None. This can be a string like 'Virgin and Martyr' for example."
    )
    saint_categories: list[str] = Field(
        description="The categories of the saint or saints in English, if applicable. If the feast is not a saint, this should be an empty list. Can be thinks like Virgin, Martyr, Doctor, Confessor, Penitent, King, Queen, etc."
    )
    saint_singular_or_plural: str | None = Field(
        description="Whether the saint is singular or plural. If the feast is not a saint, this should be None. Can be 'singular' or 'plural'."
    )


enhancement_cache = {}


def enhance(text):

    if text in enhancement_cache:
        return enhancement_cache[text]

    first = CalendarEvent.objects.filter(latin_name=text).first()
    if first:
        result = {
            "is_person": first.is_person,
            "saint_name": first.saint_name,
            "saint_category": first.saint_category,
            "saint_categories": json.loads(first.saint_categories),
            "saint_singular_or_plural": first.saint_singular_or_plural,
        }
        enhancement_cache[text] = result
        return result

    API_KEY = settings.GEMINI_API_KEY
    client = genai.Client(api_key=API_KEY)
    response = client.models.generate_content(
        # model='gemini-2.5-pro-preview-03-25',
        model="gemini-2.0-flash",
        contents=[
            f"The following is the name of a saint, feast, or commemoration in the mass. Extract data according to the schema: `{ text }`",
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=FeastName,
        ),
    )
    result = json.loads(response.candidates[0].content.parts[0].text)
    enhancement_cache[text] = result
    return result


def run():
    years = list(range(2023, 2029))
    for year in years:
        url = f"https://gcatholic.org/calendar/{year}/US-D-en"
        calendar_entries = parse_gcatholic_calendar(url)
        for entry in calendar_entries:
            if entry["name"] in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]:
                continue
            event = CalendarEvent.objects.get_or_create(
                year=entry["year"],
                month=entry["month"],
                day=entry["day"],
                english_name=entry["name"],
                calendar="current",
                subcalendar="usa",
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
            print(event.english_name)

            CalendarEvent.objects.filter(
                english_name__in=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
            ).delete()

