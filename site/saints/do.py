import json
import re
from datetime import date, timedelta
from pprint import pprint

import requests
from bs4 import BeautifulSoup, Tag
from deep_translator import ChatGptTranslator, GoogleTranslator
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from saints.models import CalendarEvent

BASE_URL = "https://www.divinumofficium.com/cgi-bin/horas/kalendar.pl"


class FeastName(BaseModel):
    feast_name: str = Field(
        description="The name of the feast or saint translated to English from Latin with no additional text or description. If there is a a common English name for this feast or saint, use that; otherwise just use a literal translation. Return just the name or translation, no additional data."
    )
    feast_translation: str | None = Field(
        description="The name of the feast or saint translated to English from Latin with no additional text or description. Use a precisely literal translation of the Latin. Return just the translation, no additional data."
    )
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


translation_cache = {}


def translate(text):

    if text in translation_cache:
        return translation_cache[text]

    first = CalendarEvent.objects.filter(latin_name=text).first()
    if first:
        result = {
            "feast_name": first.english_name,
            "feast_translation": first.english_translation,
            "is_person": first.is_person,
            "saint_name": first.saint_name,
            "saint_category": first.saint_category,
            "saint_categories": json.loads(first.saint_categories),
            "saint_singular_or_plural": first.saint_singular_or_plural,
        }
        translation_cache[text] = result
        return result

    print(text)
    API_KEY = "AIzaSyAjWoqobPToyfesczOD2fj_29xczMU6QfM"
    client = genai.Client(api_key=API_KEY)
    response = client.models.generate_content(
        # model='gemini-2.5-pro-preview-03-25',
        model="gemini-2.0-flash",
        contents=[
            f"The following is the name of a saint, feast, or commemoration in the Latin mass. Translate it from ecclesiastical Latin text to English and extract data according to the schema: `{ text }`",
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=FeastName,
        ),
    )
    result = json.loads(response.candidates[0].content.parts[0].text)
    translation_cache[text] = result
    return result


def generate_date_range(start_month, start_year, end_month, end_year):
    start = date(start_year, start_month, 1)
    end = date(end_year, end_month, 1)
    while start <= end:
        yield start.year, start.month
        start = (start.replace(day=28) + timedelta(days=4)).replace(day=1)


def parse_calendar_table(soup):
    table = soup.find("table")
    if not table:
        return []

    parsed_rows = []

    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue

        # Get plain text content for all cells first
        row_data = [td.get_text(strip=True) for td in tds]

        # Add temporale and sanctorale JSON as additional "columns"
        temporale_json = get_commemoration_data(tds[1], "temporale") if len(tds) > 1 else []
        sanctorale_json = get_commemoration_data(tds[2], "sanctorale") if len(tds) > 2 else []

        row_data.append(temporale_json)
        row_data.append(sanctorale_json)

        row_data[0] = int(row_data[0])

        parsed_rows.append(row_data)

    return parsed_rows


def clean(input_string: str) -> str:
    return " ".join(input_string.split())


def is_saint(name: str) -> bool:
    if not isinstance(name, str):
        return False

    return bool(re.search(r"(^|\s)(S\.|SS\.|Ss\.)", name))


def get_commemoration_data(cell: Tag, col_type: str) -> list:
    """
    Parses a table cell to extract commemorations from <b> and <i> tags,
    using the updated logic and JSON structure.
    """
    if not cell:
        return []

    soup = BeautifulSoup(str(cell), "html.parser")
    commemorations = []
    notes = ""
    order = 1

    # First, find and extract the notes (any tag with text ending in ':')
    for el in soup.find_all():
        if el.get_text(strip=True).endswith(":"):
            notes = el.get_text(strip=True).rstrip(":").strip()
            break  # Only the first one is used

    # Now look for <b> and <i> tags, which indicate commemorations
    for el in soup.find_all(["b", "i"]):
        tag_type = el.name
        sup = "superior" if tag_type == "b" else "subordinate"

        # Strip leading ampersand if present
        text = el.get_text(strip=True)
        if text.startswith("&"):
            text = text[1:].strip()

        # Find the <font> tag inside and extract the color + name
        font_tag = el.find("font")
        if font_tag:
            color = font_tag.get("color", "white").strip()
            name = font_tag.get_text(strip=True)
        else:
            color = "white"
            name = text  # fallback to text if font not found

        # Look ahead to next sibling for maroon font = rank
        next_el = el.find_next_sibling()
        rank = ""
        if isinstance(next_el, Tag) and next_el.name == "font":
            if next_el.get("color", "").lower() == "maroon":
                rank = next_el.get_text(strip=True)

        translation = translate(name)

        latin_notes = clean(notes)
        latin_rank = clean(rank)
        english_notes = notes_to_english(notes)
        english_rank = rank_to_english(rank, notes)
        latin_name = clean(name)
        # Build commemoration entry
        feast_object = {
            "Latin_Name": latin_name,
            "Latin_Rank": latin_rank,
            "English_Rank": english_rank,
            "Color": clean(color),
            "Latin_Notes": latin_notes,
            "English_Notes": english_notes,
            "Order": order,
            "Superior_or_Subordinate": sup,
            "Temporale_or_Sanctorale": col_type,
            "English_Name": translation["feast_name"],
            "English_Translation": translation["feast_translation"],
            "Is_Person": translation["is_person"],
            "Saint_Name": translation["saint_name"],
            "Saint_Category": translation["saint_category"],
            "Saint_Categories": translation["saint_categories"],
            "Saint_Singular_or_Plural": translation["saint_singular_or_plural"],
        }
        commemorations.append(feast_object)

        order += 1

    return commemorations


def notes_to_english(notes: str) -> str:
    notes = clean(notes)
    commemoration_dict = {
        "": "",
        "Commemoratio": "Commemoration",
        "Transfer": "Transfer",
        "Commemoratio ad Missam tantum": "Commemoration at Mass only",
        "Tempora": "Tempora",
        "Commemoratio ad Laudes tantum": "Commemoration at Lauds only",
        "Scriptura": "Scripture",
        "Commemoratio ad Laudes & Matutinum": "Commemoration at Lauds and Matins",
    }
    return commemoration_dict.get(notes, notes)


def rank_to_english(rank: str, notes: str | None) -> str:
    rank_dict = {
        "": "",
        "Duplex": "Double",
        "Duplex I. classis": "Double of the First Class",
        "Duplex II. classis": "Double of the Second Class",
        "Duplex majus": "Greater Double",
        "Duplex majus II. ordinis": "Day within an Octave, Greater Double of the Second Order",
        "Duplex majus III. ordinis": "Day within an Octave, Greater Double of the Third Order",
        "Feria": "Feria",
        "Feria major": "Major Feria",
        "Feria privilegiata": "Privileged Feria",
        "Semiduplex": "Semidouble",
        "Semiduplex Dominica I. classis": "Semidouble Sunday of the First Class",
        "Semiduplex Dominica II. classis": "Semidouble Sunday of the Second Class",
        "Semiduplex Dominica anticipata": "Anticipated Semidouble Sunday",
        "Semiduplex Dominica minor": "Minor Semidouble Sunday",
        "Semiduplex Vigilia I.classis": "Semidouble Vigil of the First Class",
        "Semiduplex Vigilia II.classis": "Semidouble Vigil of the Second Class",
        "Semiduplex Vigilia II. classis": "Semidouble Vigil of the Second Class",
        "Semiduplex Vigilia III.classis": "Semidouble Vigil of the Third Class",
        "Semiduplex II. ordinis": "Day within an Octave, Semidouble of the Second Order",
        "Semiduplex III. ordinis": "Day within an Octave, Semidouble of the Third Order",
        "Semiduplex Vigilia I. classis": "Semidouble Vigil of the First Class",
        "Simplex": "Simple",
        "I. classis": "1st Class",
        "II. classis": "2nd Class",
        "III. classis": "3rd Class",
        "IV. classis": "4th Class",
        "Dies Octavæ I. classis": "Day within an Octave, 1st Class",
    }

    value = rank_dict[rank]
    if notes and not value:
        value = notes_to_english(notes)
    return value


def scrape_divinum_officium(month, year, calendar):
    all_data = {}
    date_str = f"{month}/{year}"
    form_data = {"kyear": int(year), "kmonth": int(month), "version": calendar}
    response = requests.post(BASE_URL, data=form_data)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        table_data = parse_calendar_table(soup)
        all_data[date_str] = table_data
    else:
        print(f"Failed to fetch {date_str}")
    return all_data


def run():
    date_ranges = generate_date_range(1, 2020, 12, 2035)
    calendars = ["Divino Afflatu - 1954", "Rubrics 1960 - 1960"]
    calendars = ["Rubrics 1960 - 1960"]
    for calendar in calendars:
        for year, month in date_ranges:
            print(f"Year: {year}, Month: {month}")
            data = scrape_divinum_officium(month, year, calendar)
            for date_str, table in data.items():
                for row in table:
                    feasts = row[-1] + row[-2]
                    middle_step = sorted(
                        feasts,
                        key=lambda feast: (
                            feast["Superior_or_Subordinate"] != "superior",
                            feast["Temporale_or_Sanctorale"] != "sanctorale",
                            feast["Order"],
                        ),
                    )
                    first_type = middle_step[0]["Temporale_or_Sanctorale"]
                    feasts = sorted(
                        middle_step,
                        key=lambda feast: (
                            feast["Superior_or_Subordinate"] != "superior",
                            feast["Temporale_or_Sanctorale"] != first_type,
                            feast["Order"],
                        ),
                    )
                    for order, feast in enumerate(feasts):
                        feasts[order]["Overall_Order"] = order
                        feasts[order]["Year"] = int(year)
                        feasts[order]["Month"] = int(month)
                        feasts[order]["Day"] = int(row[0])

                        calendar_event = CalendarEvent.objects.get_or_create(
                            month=feasts[order]["Month"],
                            day=feasts[order]["Day"],
                            year=feasts[order]["Year"],
                            english_name=feast["English_Name"],
                            english_translation=feast["English_Translation"],
                            latin_name=feast["Latin_Name"],
                            color=feast["Color"],
                            latin_notes=feast["Latin_Notes"],
                            english_notes=feast["English_Notes"],
                            order=feast["Overall_Order"],
                            is_primary_for_day=feast["Superior_or_Subordinate"] == "superior",
                            temporale_or_sanctorale=feast["Temporale_or_Sanctorale"],
                            latin_rank=feast["Latin_Rank"],
                            english_rank=feast["English_Rank"],
                            is_person=feast["Is_Person"],
                            saint_name=feast["Saint_Name"],
                            saint_category=feast["Saint_Category"],
                            saint_categories=json.dumps(feast["Saint_Categories"]),
                            saint_singular_or_plural=feast["Saint_Singular_or_Plural"],
                            calendar=calendar,
                            subcalendar="",
                        )[0]
