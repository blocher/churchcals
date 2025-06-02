import time
from google import genai
from google.genai import types
import json

from google.generativeai import GenerationConfig
from pydantic import BaseModel, Field

from saints import settings
from saints.models import CalendarEvent
from typing import List
from google.genai.types import GenerationConfig, Tool, GoogleSearch
import re

def clean_json_string(response_text: str) -> str:
    """
    Removes triple backticks and optional 'json' from the start and end of the response text.
    """
    # Match patterns like ```json\n{...}\n``` or ```\n{...}\n```
    pattern = r"^```(?:json)?\n(.*)\n```$"
    match = re.match(pattern, response_text.strip(), re.DOTALL)
    if match:
        return match.group(1).strip()
    return response_text.strip()

def collect_bios():
    traditional = (CalendarEvent.objects.filter(
        calendar__in=["Divino Afflatu - 1954", "Rubrics 1960 - 1960", ]).exclude(
        english_rank__in=['Tempora', 'Scripture', 'Major Feria', 'Feria',
                          'Day within an Octave, Semidouble of the Third Order'
                          'Day within an Octave, Semidouble of the Second Order',
                          'Day within an Octave, Greater Double of the Third Order',
                          'Day within an Octave, Greater Double of the Second Order',
                          'Minor Semidouble Sunday',
                          'Anticipated Semidouble Sunday',
                          'Semidouble Sunday of the Second Class',
                          'Semidouble Sunday of the First Class',
                          'Semidouble Vigil of the First Class',
                          'Semidouble Vigil of the Second Class',
                          'Day within an Octave, 1st Class',
                          '2nd Class Feria',
                          '3rd Class Feria',
                          '4th Class Feria',
                          'Day within an Octave, 1st Class Feria',
                          'Ferial Commemoration',
                          'Ferial Commemoration at Lauds only',
                          '2nd Class Sunday',
                          'Sunday Commemoration',
                          "Commemoration Octave",
                          "Semidouble Feria",
                          "Simple Feria",
                          ]).exclude(latin_name__icontains="infra Octavam").exclude(
        english_name__icontains="Within the Octave of ").exclude(english_name__icontains="Vigil of").exclude(
        english_name__icontains="Octave Day of").exclude(english_name__icontains="Octave of").order_by(
        'english_name').values_list(
        "english_name",
        flat=True).distinct())
    print(len(traditional))

    catholic = (CalendarEvent.objects.filter(
        calendar__in=["catholic", ]).exclude(
        english_rank__in=["Feria", "Sunday"]).values_list(
        "english_name",
        flat=True).distinct())
    print(len(catholic))

    for catholic_item in catholic:
        generate_bio(catholic_item, "catholic", "catholic")
        return

    ordinariate = (CalendarEvent.objects.filter(
        calendar__in=["ordinariate", ]).exclude(
        english_rank__in=["Feria", "Sunday"]).values_list(
        "english_name",
        flat=True).distinct())
    print(len(ordinariate))

    acnas = (CalendarEvent.objects.filter(
        calendar__in=["ACNA_BCP2019", ]).exclude(
        english_rank__in=["Advent Feria", "Easter Feria", "Feria", "Lent Feria", "Rogation Day", "Ember Day",
                          "Sunday"]).values_list(
        "english_name",
        flat=True).order_by("english_name").distinct())
    print(len(acnas))

    tecs = (CalendarEvent.objects.filter(
        calendar__in=["TEC_BCP1979_LFF2024", ]).exclude(
        english_rank__in=["Advent Feria", "Easter Feria", "Feria", "Lent Feria", "Rogation Day", "Ember Day",
                          "Sunday"]).values_list(
        "english_name",
        flat=True).order_by("english_name").distinct())
    print(len(tecs))


class BibleVerse(BaseModel):
    citation: str = Field(description="The citation of the Bible verse, e.g., 'John 3:16'")
    text: str = Field(
        description="The text of the Bible verse word-for-word, e.g., 'For God so loved the world, that he gave his only Son, that whoever believes in him should not perish but have eternal life.'")
    bible_version_abbreviation: str = Field(
        description="The version of the Bible from which the verse is taken in its abbreviated form, e.g., 'ESV'")
    bible_version: str = Field(
        description="The version of the Bible from which the verse is taken in its full form, e.g., 'English Standard Version'")
    bible_version_year: str = Field(
        description="The year the Bible version was published. This should be a valid year in YYYY format.")


class Food(BaseModel):
    food_name: str = Field(description="The name of the food, dish, or drink associated with the saint or feast day")
    description: str = Field(description="The description of the food, dish, or drink")
    country_of_origin: str | None = Field(
        description="The country, region, or location of origin of the food, dish, or drink, or None if it is universal or broadly applicable")
    reason_associated_with_saint: str | None = Field(
        description="The reason the food, dish, or drink is associated with the saint or feast day, or None if there is no specific reason")


class Foods(BaseModel):
    foods: List[Food] | None = Field(
        description="List of foods associated with the saint or feast day, or None if no foods are associated, sort with most common or popular at the top of the list.")


class Tradition(BaseModel):
    tradition: str = Field(description="The tradition or custom associated with the saint or feast day")
    country_of_origin: str | None = Field(
        description="The country, region, or location of origin of the tradition or custom, or None if it is universal or broadly applicable")
    reason_associated_with_saint: str | None = Field(
        description="The reason the tradition or custom is associated with the saint or feast day, or None if there is no specific reason")


class Traditions(BaseModel):
    traditions: List[Tradition] | None = Field(
        description="List of pious or popular traditions associated with the saint or feast day, or None if no traditions are associated")


class Quote(BaseModel):
    quote: str = Field(
        description="The quote by or about the saint, word for word as it was originally written or spoken without any modifications, except to be literally translated into English if needed.")
    person: str = Field(description="The person who made this quote)")
    date: str = Field(
        description="The exact date if known (with fallbacks to the year, century, or time-period, if not known) when the quote was made in a publishable, human-readable format")


class ShortDescriptions(BaseModel):
    one_sentence_description: str = Field(
        description="An exactly one-sentence description of the saint or feast day, summarizing their significance or role in Christianity")
    one_paragraph_description: str = Field(
        description="An exactly one-paragraph description of the saint or feast day, providing a brief overview of their life, contributions, and significance in Christianity")


class HagiographyCitation(BaseModel):
    citation: str = Field(description="The citation, including the author and source, if available")
    url: str | None = Field(
        description="The URL where the source can be found, if available, or None if not applicable. This must be a valid URL.")
    date_accessed: str | None = Field(
        description="The date when the source was accessed, if applicable, or None if not applicable")
    title: str | None = Field(description="The title of the article, website, or source.")


class Hagiography(BaseModel):
    hagiography: str = Field(
        description="A detailed hagiographical biography of the saint or feast day, at least 500 words long (and up to 1,500 words), providing an in-depth look at their life, contributions, and significance in Christianity")
    citations: List[HagiographyCitation] | None = Field(
        description="List of citations for the hagiography, if available, or None if not applicable")


class Legend(BaseModel):
    legend: str = Field(
        description="A story, anecdote, or pious legend from the life of the saint or feast day, written in a narrative, dramatic style. It should be interesting and revealing of their character and faith.")
    title: str = Field(description="A short, creative title for the legend or story")
    citations: List[HagiographyCitation] | None = Field(
        description="List of citations for the legend, if available, or None if not applicable")


class BulletPoints(BaseModel):
    bullet_points: List[str] = Field(
        description="A list of 4-6 short bullet points summarizing the life and contributions of the saint or feast day to the Christian life, each point should be concise and informative.")
    citations: List[HagiographyCitation] | None = Field(
        description="List of citations for the bullet points, if available, or None if not applicable")


class Writing(BaseModel):
    writing: str = Field(
        description="Word-for-word original text of the writing (literally translated into English if necessary. This should be on the longer-side (300-4000 words).")
    date: str = Field(
        description="The exact date if known (with fallbacks to the year, century, or time-period, if not known) when the quote was made in a publishable, human-readable format")
    title: str = Field(description="The title of the writing")
    url: str | None = Field(
        description="The URL where the source can be found, if available, or None if not applicable. This must be a valid URL.")
    author: str | None = Field(description="The author of the writing, if known, or None if not applicable")


class Writings(BaseModel):
    writing_by_saint: Writing | None = Field(
        description="A representative writing by the saint that best articulates their beliefs, teachings, or contributions to Christianity. This should be a word-for-word original text of the writing (literally translated into English if necessary). Aim for 300-4000 words.")
    writing_about_saint: Writing | None = Field(
        description="A representative writing about the saint or his/her contribution by a different author the saint that best articulates their beliefs, teachings, or contributions to Christianity. This should be a word-for-word original text of the writing (literally translated into English if necessary). Aim for 300-4000 words.")


class Image(BaseModel):
    url: str = Field(description="The URL to the image, which must be a valid URL")
    title: str = Field(description="The title of the image")
    author: str | None = Field(description="The author of the image, or None if not applicable")
    date: str | None = Field(description="The date when the image was created, if known, or None if not applicable")


class Images(BaseModel):
    images: List[Image] | None = Field(
        description="List of 3-5 images of the saint or feast day that are in the public domain or have a Creative Commons license. Each image should include the URL to the image, the title of the image, and the author of the image. If there are no images, return None.")


def generate_bio(person: str, religion: str, calendar: str):
    agent_string = {
        "catholic": "You are a Roman Catholic who is fully obedient to the magisterium of the Catholic Church, and familiar with the Catholic patrimony, traditions, and beliefs.",
        "ordinariate": "You are a Roman Catholic who is fully obedient to the magisterium of the Catholic Church, a member of the Anglican Ordinariate, and familiar with the Anglican patrimony, especially the Book of Divine Worship and the Anglican Use of the Roman Rite.",
        "acna": "You are a member of the Anglican Church in North America, obedient to the Anglican formularies such as the Book of Common Prayer and the 39 Articles. You are not a member of the Episcopal Church in the United States.",
        "tec": "You are a member of the Episcopal Church in the United States, part of the worldwide Anglican Communion, familiar with the Anglican tradition and the modern Episcopal Church.",
        "traditional": "You are a traditional Roman Catholic who is fully obedient to the magisterium of the Catholic Church and in communion with the Pope, steeped in the tradition of the Traditional Latin Mass and the pre-1970 Roman Rite (especially the 1954 or 1960 calendar), and familiar with the Catholic patrimony. You may belong to a traditional society like the FSSP or ICKSP, or be a layperson who attends the Traditional Latin Mass.",
    }

    religion_string = {
        "catholic": "the Roman Catholic Church",
        "ordinariate": "the Roman Catholic Church, especially the Anglican Ordinariate",
        "acna": "the Anglican Church in North America",
        "tec": "the Episcopal Church in the United States",
        "traditional": "the Roman Catholic Church who attends the Traditional Latin Mass",
    }

    bible_version = {
        "catholic": "New American Bible (NAB) (1970)",
        "ordinariate": "Revised Standard Version, Second Catholic Edition (RSV2CE) (2006)",
        "acna": "English Standard Version (ESV) (2025)",
        "tec": "New Revised Standard Version (NRSV) (1989)",
        "traditional": "Douay-Rheims Bible (Challoner Revision) (DRC) (1752)",
    }

    # Initialize the GenAI client
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # Define the model name
    model_name = "gemini-2.5-flash-preview-05-20"

    # Define the system instruction
    system_instruction = agent_string[religion]

    # Define the prompts
    prompts = [
        (
            "short_descriptions",
            ShortDescriptions,
            f"Provide two very short descriptions of who {person} is, one that is a single sentence long and one that is a single paragraph long. Include what the person is known for and their role in the Christian life and church, especially from the perspective of someone in {religion_string[religion]}. You don't need to include the name of the religion (you can assume the reader is {religion_string[religion]}).",
        ),
        (
            "quotes",
            Quote,
            f"List one quote either by or about {person} that best represents them and their importance to Christianity.",
        ),
        (
            "verse",
            BibleVerse,
            f"What is one Bible verse in {bible_version[religion]} that best represents the life, work, and beliefs of {person}? Include the exact quote with book, chapter, and verse, and version of the Bible.",
        ),
        (
            "ai_hagiography",
            Hagiography,
            f"Write a hagiographical biography of {person} that is at least 6 paragraphs and 600 words and is rather detailed. Include just the biography—no intro text or other text. It should be an engaging narrative of the person's life and why they are important in the Christian tradition, especially from the perspective of someone in {religion_string[religion]}.",
        ),
        (
            "ai_legend",
            Legend,
            f"Tell a story, anecdote, or pious legend from the life of {person} that is interesting and revealing of their character and faith. Include just the title and story—no intro text or other text. Tell it as a storyteller with a narrative, dramatic style.",
        ),
        (
            "ai_bullet_points",
            BulletPoints,
            f"Summarize {person}'s life and contributions to the Christian life in 4-6 short bullet points. Include just the bullet points—no intro text or other text. Include important events, contributions, and beliefs that are significant in the Christian tradition, especially from the perspective of someone in {religion_string[religion]}.",
        ),
        (
            "ai_traditions",
            Traditions,
            f"Include a bulleted list of interesting traditions for the feast day of {person} from around the world with which country they are from. If there is nothing notable, return None. Do not use the first person ever. Include just the bullet points—no intro text or other text.",
        ),
        (
            "ai_foods",
            Foods,
            f"Include a bulleted list of interesting foods or culinary habits for the feast day of {person} from around the world with which country they are from. If there is nothing notable, return None. Do not use the first person ever. Include just the bullet points—no intro text or other text.",
        ),
        (
            "ai_writings",
            Writings,
            f"Include two representative writings by {person} that best articulate their beliefs, teachings, or contributions to Christianity (one by the saint, if there is one, and one about the saint, if there is one). This should be a word-for-word original text of the writing (literally translated into English if necessary). Aim for 300-4000 words. Include just the writing—no intro text or other text.",
        ),
        (
            "images",
            Images,
            f"Return 3-5 images of {person} that are in the public domain or have a Creative Commons license. Include the URL to the image, the title of the image, and the author of the image. If there are no images, return none.",
        ),
    ]

    conversation_history = []
    for p_name, p_model, p_text in prompts:
        # Construct the formatted prompt with JSON schema
        json_instruction = f"Use Google Search for every factual claim and cite your sources in the citation_metadata for all factual claims, and include a citation for every paragraph or fact whenever possible (in the citation_metadata attribute, not the content response). Format your response as valid JSON that conforms to this schema: {p_model.schema_json()}"
        formatted_prompt = f"{p_text}\n\n{json_instruction}"

        # Add the new user message to the conversation history
        user_message = {"role": "user", "parts": [{"text": formatted_prompt}]}
        conversation_history.append(user_message)

        # Define the generation configuration
        generation_config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7,
            max_output_tokens=65535,
            # tools=[Tool(google_search=GoogleSearch())],
            response_mime_type="application/json",
            response_schema=p_model,
        )

        # Attempt to generate content with retries
        response = None
        for attempt in range(5):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=conversation_history,
                    config=generation_config,
                )
                break
            except Exception as e:
                print(f"Error during Gemini API call for {p_name} (attempt {attempt + 1}/5): {e}")
                if attempt < 4:
                    time.sleep(0.5 * (attempt + 1))
                else:
                    print(f"Failed to get {p_name} for {person} after 5 attempts.")
                    continue

        if not response or not response.candidates:
            print(f"Failed to get a valid response for {p_name} for {person} from Gemini.")
            continue

        # Extract the response text
        response_text = response.candidates[0].content.parts[0].text
        cleaned_response_text = clean_json_string(response_text)

        try:
            completion_result = p_model.model_validate_json(cleaned_response_text)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse JSON response for {p_name} for {person}: {e}")
            print(f"[ERROR] Raw response text: {cleaned_response_text}")
            continue
        except Exception as e:
            print(f"[ERROR] Validation or parsing error for {p_name} for {person}: {e}")
            print(f"[ERROR] Raw response text: {cleaned_response_text}")
            continue

        # Add the model's response to the conversation history
        model_message = {"role": "model", "parts": [{"text": response_text}]}
        conversation_history.append(model_message)

        # Print the completion result
        print(f"=== {p_name} ===")
        print("Completion result:", completion_result)

        # Handle citations if available
        citation_metadata = response.candidates[0].citation_metadata
        print("Citations (Annotations):")
        if citation_metadata and getattr(citation_metadata, 'citations', None):
            for source in citation_metadata.citations:
                print(f"  - Start Index: {getattr(source, 'start_index', 'N/A')}, "
                      f"End Index: {getattr(source, 'end_index', 'N/A')}, "
                      f"URI: {getattr(source, 'uri', 'N/A')}, "
                      f"License: {getattr(source, 'license', 'N/A')}")
        else:
            print("  None")
