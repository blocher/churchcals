import json
import os
from datetime import date, timedelta
from enum import Enum, IntEnum
from pprint import pprint

from django.conf import settings
from openai import OpenAI
from pydantic import BaseModel, Field
from saints.models import CalendarEvent

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def all_dates():
    from datetime import date, timedelta

    # Start from Jan 1 of a leap year
    start_date = date(2020, 1, 1)  # Leap year
    end_date = date(2020, 12, 31)

    date_tuples = []

    current_date = start_date
    while current_date <= end_date:
        month_name = current_date.strftime("%B")
        date_tuples.append((month_name, current_date.day))
        current_date += timedelta(days=1)

    return date_tuples


class SaintTitleEnum(str, Enum):
    saint = "Saint"
    saints = "Saints"
    blessed = "Blessed"
    blesseds = "Blesseds"
    venerable = "Venerable"


class Rank1954(str, Enum):
    double_of_I_class = "Double of the I Class"
    double_of_II_class = "Double of the II Class"
    major_double = "Major Double (Greater Double)"
    double = "Double"
    semidouble = "Semidouble"
    simple = "Simple"
    greater_privileged_feria = "Greater Privileged Feria"
    greater_non_privileged_feria = "Greater Non-Privileged Feria"
    lesser_feria = "Lesser Feria"
    privileged_octave_of_first_order = "Privileged Octave of the First Order"
    privileged_octave_of_second_order = "Privileged Octave of the Second Order"
    privileged_octave_of_third_order = "Privileged Octave of the Third Order"
    common_octave = "Common Octave"
    simple_octave = "Simple Octave"
    privileged_vigil = "Privileged Vigil"
    common_vigil = "Common Vigil"
    commemoration = "Commemoration"


class Rank1960(str, Enum):
    feast_of_the_first_class = "Feast of the First Class"
    feast_of_the_second_class = "Feast of the Second Class"
    feast_of_the_third_class = "Feast of the Third Class"
    feria_of_the_first_class = "Feria of the First Class"
    feria_of_the_second_class = "Feria of the Second Class"
    feria_of_the_third_class = "Feria of the Third Class"
    feria_of_the_fourth_class = "Feria of the Fourth Class"
    octave_day = "Octave Day"
    commemoration = "Commemoration"


class Rank1969(str, Enum):
    solemnity = "Solemnity"
    feast = "Feast"
    memorial = "Memorial"
    optional_memorial = "Optional Memorial"
    seasonal_weekday = "Seasonal Weekday"
    feria = "Feria"


class CalendarEnum(str, Enum):
    roman_rite_1954 = "Roman Rite (1954)"
    roman_rite_1962 = "Roman Rite (1962)"
    current_roman_rite = "Roman Rite (Current)"
    ordinariate_roman_rite = "Roman Rite (Ordinariate)"


class SubcalendarEnum(str, Enum):
    general = "General"
    australia_and_new_zealand = "Australia and New Zealand"
    brazil = "Brazil"
    canada = "Canada"
    england_and_wales = "England and Wales"
    france = "France"
    korea = "Korea"
    philippines = "Philippines"
    poland = "Poland"
    portugal = "Portugal"
    scotland = "Scotland"
    spain = "Spain"
    united_states = "United States"
    vietnam = "Vietnam"
    fssp = "FSSP"
    icksp = "ICKSP"
    sspx = "SSPX"
    in_some_places = "In Some Places"


class FeastTypeEnum(str, Enum):
    event_in_life_of_christ = "Event in the life of Christ"
    day_within_the_octave = "Day within the Octave"
    other_event = "Other Event"
    title_apparition_or_feast_of_bvm = "Title, Apparition, or Feast of the Blessed Virgin Mary"
    saint = "Saint"
    other = "Other"


class Feast(BaseModel):
    month: int | None = Field(
        description="Month the saint is commemorated on the calendar as an integer from 1 to 12, None if the date is variable"
    )
    day: int | None = Field(
        description="Day of the month the saint is commemorated on the calendar as an integer from 1 to 31, None if the date is variable"
    )
    name: str = Field(description="Name of the feast or saint")
    saint_name: str | None = Field(
        description="Name of the saint or saint alone. For example St. John the Evangelist would return just John. Only return if the event is a pereson."
    )
    title: SaintTitleEnum | None = Field(
        description="Title of the saint. Options are Saint, Saints, Blessed, Blesseds, Venerable. Saint may be identified by St, Saints by SS or Sts., blessed by Bd., Blesseds by BB or Bds., Venerable, etc., None if not applicable"
    )
    saint_description_string: str | None = Field(
        description="Category or categories of the saint such as 'Bishop and Martyr', 'Martyr', 'Confessor', 'Virgin', 'King', 'Queen', 'Penitent', 'Bishop', 'Archbishop', etc., None if not a person"
    )
    saint_categories: list[str] = Field(
        description="List of categories of the saint such as 'Bishop and Martyr', 'Martyr', 'Confessor', 'Virgin', 'King', 'Queen', 'Penitent', 'Bishop', 'Archbishop', etc., Empty list if not a person"
    )
    calendar: CalendarEnum = Field(
        description="The calendar the saint is commemorated in. Options are 'Roman Rite (1954)', 'Roman Rite (1962)', 'Roman Rite (Current)', 'Roman Rite (Ordinariate)'"
    )
    subcalendar: SubcalendarEnum = Field(
        description="The sub=calendar the saint is commemorated in. Options are 'General', 'USA', 'FSSP', 'ICKSP', 'SSPX', or 'In Some Places'"
    )
    event_type: FeastTypeEnum = Field(
        description="The type of feast, either 'Event in the life of Christ', 'Other Event', 'Title, Apparition, or Feast of the Blessed Virgin Mary', 'Saint', 'Other'"
    )


class Feast1954(Feast):
    rank: Rank1954 = Field(description="Rank of the feast")


class Feast1960(Feast):
    rank: Rank1960 = Field(description="Rank of the feast")


class Feast1969(Feast):
    rank: Rank1969 = Field(description="Rank of the feast")


class Feasts1954(BaseModel):
    feasts: list[Feast1954] = Field(description="List of saints or feasts extracted from the document")


class Feasts1960(BaseModel):
    feasts: list[Feast1960] = Field(description="List of saints or feasts extracted from the document")


class Feasts1969(BaseModel):
    feasts: list[Feast1969] = Field(description="List of saints or feasts extracted from the document")


def retrieve_document_content(document_name):
    try:
        print(f"saints/documents/{document_name}.txt")
        with open(f"saints/documents/{document_name}.txt", "r") as file:
            return file.read()
    except FileNotFoundError:
        return None


def get_one_day(input_text, calendar):

    if calendar == "1954":
        response_format = Feasts1954
    elif calendar == "1960":
        response_format = Feasts1960
    else:
        response_format = Feasts1969
    content = retrieve_document_content(calendar)
    instructions = f"You are a helpful assistant to answer questions about the liturgical calendar. Use the following document to answer the user's query:\n\n{content}"

    completion = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[{"role": "system", "content": instructions}, {"role": "user", "content": input_text}],
        response_format=response_format,
    )

    return json.loads(completion.choices[0].message.content).get("feasts", [])


def get_each_feast():
    dates = all_dates()
    # dates = [("January", 11)]
    for month, day in dates:
        print(month, day)
        res = get_one_day(
            f"List all the events for {month} {day}. Only include ones in the provided text. Note that 'Com. of ' always means a separate event and should be treated as such.",
            "1969",
        )
        pprint(res)
        for event in res:
            calendar_event = CalendarEvent.objects.get_or_create(
                month=event["month"],
                day=event["day"],
                name=event["name"],
                calendar=event["calendar"],
                subcalendar=event["subcalendar"],
            )[0]
            calendar_event.month = event["month"]
            calendar_event.day = event["day"]
            calendar_event.name = event["name"]
            calendar_event.saint_name = event["saint_name"]
            calendar_event.title = event["title"]
            calendar_event.saint_description_string = event["saint_description_string"]
            calendar_event.saint_categories = event["saint_categories"]
            calendar_event.rank = event["rank"]
            calendar_event.calendar = event["calendar"]
            calendar_event.subcalendar = event["subcalendar"]
            calendar_event.type = event["event_type"]
            calendar_event.save()
