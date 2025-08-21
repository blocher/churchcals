"""
Podcast generation using ElevenLabs Turbo v2.5 TTS

Voice Configuration:
The script uses predefined voice IDs for different podcast hosts. The current configuration uses:
- John: Jeff voice (gs0tAILXbY5DNrJrsM6F) - warm male voice
- Maria: Vivie 2 Upbeat voice (H1GhCI6GEKiSXZcwmUkc) - clear female voice

To customize voices:
1. Browse the ElevenLabs Voice Library or create your own voices
2. Copy the voice IDs from your ElevenLabs dashboard
3. Update the voice_config dictionary in the generate_tts_and_merge function

Voice Instructions Processing:
The script automatically processes voice instructions in square brackets (like [laughs], [softly]) 
and converts them to appropriate ElevenLabs voice settings:
- Voice instructions are REMOVED from the text before TTS generation
- Instructions are mapped to stability, style, and speed settings
- Examples: [softly] → slower, more stable; [dramatically] → faster, more expressive
- This prevents ElevenLabs from reading the instructions literally

For best results with Turbo v2.5:
- Choose voices with good emotional range and clarity
- Consider creating custom voices tailored to your podcast style
- The model provides excellent quality with faster generation times
- Voices are balanced for clear, natural delivery without distortion
"""


from pprint import pprint
from django_cron import CronJobBase, Schedule


# Configuration: AI Model Selection
# Set to 'openai' for GPT-5, 'grok' for Grok 2, or 'anthropic' for Claude
AI_MODEL_PROVIDER = 'openai'  # Options: 'openai', 'grok', 'anthropic'

# Model configurations
MODEL_CONFIG = {
    'openai': {
        'model': 'gpt-5',
        'client_module': 'openai',
        'client_class': 'OpenAI'
    },
    'grok': {
        'model': 'grok-2-1212',
        'client_module': 'openai',  # Grok uses OpenAI-compatible API
        'client_class': 'OpenAI',
        'base_url': 'https://api.x.ai/v1',
        'api_key_env': 'XAI_API_KEY'
    },
    'anthropic': {
        'model': 'claude-opus-4-1-20250805',
        'client_module': 'anthropic',
        'client_class': 'Anthropic',
        'api_key_env': 'ANTHROPIC_API_KEY'
    }
}


def get_ai_client():
    """
    Get the appropriate AI client based on the configured provider.
    """
    config = MODEL_CONFIG[AI_MODEL_PROVIDER]
    
    if AI_MODEL_PROVIDER == 'openai':
        from openai import OpenAI
        return OpenAI()
    elif AI_MODEL_PROVIDER == 'grok':
        from openai import OpenAI
        api_key = os.getenv(config['api_key_env'])
        if not api_key:
            raise ValueError(f"{config['api_key_env']} environment variable is required for Grok")
        return OpenAI(
            api_key=api_key,
            base_url=config['base_url']
        )
    elif AI_MODEL_PROVIDER == 'anthropic':
        from anthropic import Anthropic
        api_key = os.getenv(config['api_key_env'])
        if not api_key:
            raise ValueError(f"{config['api_key_env']} environment variable is required for Anthropic")
        return Anthropic(api_key=api_key)
    else:
        raise ValueError(f"Unsupported AI model provider: {AI_MODEL_PROVIDER}")


def get_model_name():
    """
    Get the model name for the configured provider.
    """
    return MODEL_CONFIG[AI_MODEL_PROVIDER]['model']


def create_structured_completion(client, model, messages, response_format_model):
    """
    Create a structured completion that works with OpenAI, Grok, and Anthropic.
    For OpenAI, uses the .parse() method with Pydantic models.
    For Grok and Anthropic, falls back to JSON mode and manual parsing.
    """
    if AI_MODEL_PROVIDER == 'openai':
        # Use OpenAI's structured output with .parse()
        response = client.beta.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=response_format_model,
        )
        return response.choices[0].message.parsed
    elif AI_MODEL_PROVIDER == 'anthropic':
        # Use Anthropic's API with JSON mode
        enhanced_messages = messages.copy()
        system_message = None
        
        # Extract system message if present
        if enhanced_messages and enhanced_messages[0]["role"] == "system":
            system_message = enhanced_messages[0]["content"]
            enhanced_messages = enhanced_messages[1:]  # Remove system message from messages array
            
            # Create a simplified schema description for Anthropic
            if hasattr(response_format_model, '__name__') and response_format_model.__name__ == 'KidsPodcastScriptModel':
                schema_description = '{"title": "string", "saint_name": "string", "characters": ["string"], "script_lines": [{"character": "string", "text": "string"}], "voices": [{"character": "string", "voice_id": "string"}]}'
            elif hasattr(response_format_model, '__name__') and response_format_model.__name__ == 'PodcastScriptModel':
                schema_description = '{"lines": [{"character": "string", "text": "string"}]}'
            elif hasattr(response_format_model, '__name__') and response_format_model.__name__ == 'StructuredResponse':
                schema_description = '{"feasts": [{"Title": "string", "Calendars": ["string"], "Summary": "string", "Themes": ["string"], "CommemorationIdeas": ["string"], "DiscussionQuestion": "string", "Traditions": ["string"]}, ...]}'
            elif hasattr(response_format_model, '__name__') and response_format_model.__name__ == 'ResearchQueryModel':
                schema_description = '{"queries": ["string", ...]}'
            else:
                # Fallback to a generic structure
                schema_description = str(response_format_model.model_json_schema())
            system_message += f"\n\nIMPORTANT: Return your response as valid JSON that matches this exact structure: {schema_description}"
        
        # Create the API call with or without system message
        print(f"[DEBUG] Anthropic API call - Model: {model}, System message length: {len(system_message) if system_message else 0}, Messages: {len(enhanced_messages)}")
        
        if system_message:
            response = client.messages.create(
                model=model,
                max_tokens=8000,  # Increased token limit for complex responses
                system=system_message,
                messages=enhanced_messages
            )
        else:
            response = client.messages.create(
                model=model,
                max_tokens=8000,  # Increased token limit for complex responses
                messages=enhanced_messages
            )
        
        print(f"[DEBUG] Anthropic response received - Usage: {getattr(response, 'usage', 'N/A')}")
        content = response.content[0].text
        if isinstance(content, str):
            import json
            print(f"[DEBUG] Anthropic response content: {content[:500]}...")  # Show first 500 chars
            
            # Check if content is empty or whitespace
            if not content.strip():
                raise ValueError("Anthropic returned empty response")
            
            try:
                parsed_json = json.loads(content)
                # Create instance of the response format model from the JSON
                return response_format_model.model_validate(parsed_json)
            except json.JSONDecodeError as e:
                print(f"[ERROR] Failed to parse JSON from Anthropic response: {e}")
                print(f"[ERROR] Raw content: {repr(content)}")
                raise ValueError(f"Anthropic returned invalid JSON: {e}") from e
        return content
    else:
        # Use JSON mode for Grok and manually parse
        # Update the system message to include JSON schema instructions for Grok
        enhanced_messages = messages.copy()
        if enhanced_messages and enhanced_messages[0]["role"] == "system":
            # Create a simplified schema description instead of the full JSON schema
            if hasattr(response_format_model, '__name__') and response_format_model.__name__ == 'KidsPodcastScriptModel':
                schema_description = '{"title": "string", "saint_name": "string", "characters": ["string"], "script_lines": [{"character": "string", "text": "string"}], "voices": [{"character": "string", "voice_id": "string"}]}'
            elif hasattr(response_format_model, '__name__') and response_format_model.__name__ == 'PodcastScriptModel':
                schema_description = '{"lines": [{"character": "string", "text": "string"}]}'
            elif hasattr(response_format_model, '__name__') and response_format_model.__name__ == 'StructuredResponse':
                schema_description = '{"feasts": [{"Title": "string", "Calendars": ["string"], "Summary": "string", "Themes": ["string"], "CommemorationIdeas": ["string"], "DiscussionQuestion": "string", "Traditions": ["string"]}, ...]}'
            elif hasattr(response_format_model, '__name__') and response_format_model.__name__ == 'ResearchQueryModel':
                schema_description = '{"queries": ["string", ...]}'
            else:
                # Fallback to a generic structure
                schema_description = str(response_format_model.model_json_schema())
            enhanced_messages[0]["content"] += f"\n\nIMPORTANT: Return your response as valid JSON that matches this exact structure: {schema_description}"
        
        response = client.chat.completions.create(
            model=model,
            messages=enhanced_messages,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        if isinstance(content, str):
            import json
            parsed_json = json.loads(content)
            # Create instance of the response format model from the JSON
            return response_format_model.model_validate(parsed_json)
        return content


import datetime
import os
import io
import json
import tempfile
import subprocess
import string
import requests
from datetime import date
from typing import List, Dict, Any
from pydantic import BaseModel, field_validator, model_validator
import openai
from elevenlabs.client import ElevenLabs
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import make_aware, get_default_timezone
from saints.models import CalendarEvent
from saints.api import BiographySerializer
from django.utils.text import slugify
from saints.models import Podcast, PodcastEpisode

# Add Google Search API imports
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# Valid ElevenLabs voice IDs that the AI must choose from (kept in sync with the system prompt)
ALLOWED_ELEVENLABS_VOICE_IDS = {
    "7tRwuZTD1EWi6nydVerp",  # Main Blurb Narrator (male)
    "cfc7wVYq4gw4OpcEEAom",  # Main Story Narrator (female)
    "vfaqCOvlrKi4Zp7C2IAm",  # Evil, Demonic, Creepy (male)
    # "piI8Kku0DcvcL6TTSeQt",  # Fairy-like, Chipper, Squeaky, High-pitched, Childlike (female)
    "yjJ45q8TVCrtMhEKurxY",  # Mad Scientist, Quirky (male)
    "oR4uRy4fHDUGGISL0Rev",  # Wise, Wizard, Merlin, Magic, Use Sparingly (male)
    "PPzYpIqttlTYA83688JI",  # Pirate, Adventerous (male)
    # "pPdl9cQBQq4p6mRkZy2Z",  # Girly, Giggly, Young (female)
    "ZF6FPAbjXT4488VcRRnw",  # Young, British, Bookworm (female)
    # "FF7KdobWPaiR0vkcALHF",  # Epic, Voice of God, Movie narrator (male)
    # "dHd5gvgSOzSfduK4CvEg",  # Comedy announcer, Jimmy Fallon (male)
    "y2Y5MeVPm6ZQXK64WUui",  # Old, Storyteller, Wise (male)
    # "H8BjWxFjrzNszTO74noq",  # Girly, Young, Storyteller (female)
    "Wu86LpENEn32PwtU2hv1",  # Deeper, Cheery (female)
    "FUfBrNit0NNZAwb58KWH",  # Generic, Main Character (female)
    "EkK5I93UQWFDigLMpZcX",  # Deep, Main Character, Narrator (male)
    "qBDvhofpxp92JgXJxDjB",  # Female, calmoing, youthful (female)
    "c7XGL37TTXR5zdorzHX9",  # Gossipy, Sassy, Teenager (female)
    "3vk47KpWZzIrWkdEhumS",  # Chatty, Laid back (male)
    "b3tuFWghbXYRa9Cs9MJf",  # Narrator, Deep (male)
    "0TfZ4rvne3QI7UjDxVkM",  # Childlike, High pitched (female)
    
    
}
class ScriptLineModel(BaseModel):
    character: str
    text: str


class VoiceAssignment(BaseModel):
    character: str
    voice_id: str

    @field_validator("voice_id")
    @classmethod
    def validate_voice_id(cls, v: str) -> str:
        if v not in ALLOWED_ELEVENLABS_VOICE_IDS:
            raise ValueError("voice_id must be one of the allowed ElevenLabs voice IDs")
        return v


class KidsPodcastScriptModel(BaseModel):
    title: str
    saint_name: str
    characters: List[str]
    script_lines: List[ScriptLineModel]
    voices: List[VoiceAssignment]

    @model_validator(mode="after")
    def validate_voices_cover_characters(self) -> "KidsPodcastScriptModel":
        character_set = {c.strip().lower() for c in self.characters}
        assigned = {v.character.strip().lower() for v in self.voices}
        missing = character_set - assigned
        if missing:
            # Convert back to original case for error message
            original_missing = [c for c in self.characters if c.strip().lower() in missing]
            raise ValueError(f"Missing voice assignments for characters: {', '.join(sorted(original_missing))}")
        
        # Ensure script lines only use declared characters (case-insensitive comparison)
        line_characters = {l.character.strip().lower() for l in self.script_lines}
        unknown = line_characters - character_set
        if unknown:
            # Get the original character names that are unknown
            original_unknown = [l.character for l in self.script_lines if l.character.strip().lower() in unknown]
            raise ValueError(f"script_lines reference undeclared characters: {', '.join(sorted(set(original_unknown)))}")
        return self


class StructuredBioModel(BaseModel):
    Title: str
    Calendars: List[str]
    Summary: str
    Themes: List[str]
    CommemorationIdeas: List[str]
    DiscussionQuestion: str
    Traditions: List[str] = []


class ResearchQueryModel(BaseModel):
    queries: List[str]


class StructuredResponse(BaseModel):
    feasts: List[StructuredBioModel]


class PodcastScriptModel(BaseModel):
    lines: List[ScriptLineModel]


# Helper Functions

def generate_podcast_filename(target_date: date) -> str:
    """
    Generate a unique filename for a podcast episode based on the target date.
    Ensures the filename is unique in the media storage by adding suffixes if needed.
    
    Args:
        target_date: The date for which to generate the filename
        
    Returns:
        A unique filename string for the podcast episode
    """
    date_str = target_date.strftime("%Y_%m_%d")
    base_filename = f"saints_and_seasons_{date_str}.mp3"
    filename = base_filename
    suffix_iter = iter(string.ascii_lowercase)
    podcasts_dir = "podcasts/"
    
    # Ensure unique filename in the media storage
    while default_storage.exists(os.path.join(podcasts_dir, filename)):
        suffix = next(suffix_iter)
        filename = f"saints_and_seasons_{date_str}_{suffix}.mp3"
    
    return filename


def get_biographies_for_day(target_date: date) -> List[Dict[str, Any]]:
    print("[START] get_biographies_for_day")
    # Calendar priority order (most important first)
    calendar_priority = [
        "catholic",                 # 1. General Catholic calendar (highest priority)
        "Divino Afflatu - 1954",   # 2. Traditional 1954
        "Rubrics 1960 - 1960",     # 3. Traditional 1960
        "ordinariate",              # 4. Ordinariate (lowest priority)
    ]
    
    events = CalendarEvent.objects.filter(date=target_date, calendar__in=calendar_priority)
    if not events.exists():
        print("No biographies found for this day.")
        return []
    
    # Group events by calendar for prioritized ordering
    events_by_calendar = {}
    for event in events:
        if hasattr(event, 'biography') and event.biography:
            calendar = event.calendar
            if calendar not in events_by_calendar:
                events_by_calendar[calendar] = []
            events_by_calendar[calendar].append(event.biography)
    
    # Build prioritized list of biographies
    prioritized_biographies = []
    for calendar in calendar_priority:
        if calendar in events_by_calendar:
            prioritized_biographies.extend(events_by_calendar[calendar])
    
    data = BiographySerializer(
        prioritized_biographies,
        many=True
    ).data
    print("[END] get_biographies_for_day")
    return data


def identify_research_queries(bios: List[Dict[str, Any]]) -> List[str]:
    print("[START] identify_research_queries")
    client = get_ai_client()
    prompt = (
        "You are preparing a podcast targeted at kids aged 4-16 about today's Catholic saints and feasts that gives a short biography followed by a dramatic audio drama of a story or legend from the life of the saint or related to the feast. Based on the following data, identify 1–4 factual questions a good host might research to make the show more informative, interesting, or engaging, focusing on colecting dramatic stories. Return only a JSON object with a 'queries' key containing a list of strings."
    )

    result = create_structured_completion(
        client=client,
        model=get_model_name(),
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt + "\n" + json.dumps(bios)}
        ],
        response_format_model=ResearchQueryModel
    )

    print("[DEBUG] AI response result:")
    print("[END] identify_research_queries")
    return result.queries


def supplement_with_searches(queries: List[str]) -> List[Dict[str, str]]:
    """
    Use Google Search API to find current, factual information about saints and feasts.
    Combines Google Search with AI assistance to provide relevant, engaging summaries.
    """
    print("[START] supplement_with_searches")
    
    # Get Google Search API credentials from environment
    google_api_key = os.getenv('GOOGLE_SEARCH_API_KEY')
    google_cse_id = os.getenv('GOOGLE_CUSTOM_SEARCH_ENGINE_ID')
    
    if not google_api_key or not google_cse_id:
        print("Warning: Google Search API credentials not found. Using AI-only research.")
        return _fallback_ai_research(queries)
    
    results = []
    
    for query in queries:
        try:
            # Perform Google Search
            search_results = _perform_google_search(query, google_api_key, google_cse_id)
            print("SEARCH RESULTS", search_results, "SEARCH_RESULTS_END")
            # Use AI to synthesize and summarize the search results
            summary = _synthesize_search_results(query, search_results)
            results.append({
                "query": query,
                "summary": summary,
                "sources": [result.get('link', '') for result in search_results[:3]]  # Top 3 sources
            })
            
        except Exception as e:
            print(f"Error processing query '{query}': {e}")
            # Fallback to AI-only research for this query
            ai_summary = _fallback_ai_research([query])[0]["summary"]
            results.append({
                "query": query,
                "summary": ai_summary,
                "sources": []
            })
    
    print(f"[DEBUG] Generated {len(results)} search summaries")
    # print("[END] supplement_with_searches")
    return results


def _perform_google_search(query: str, api_key: str, cse_id: str) -> List[Dict[str, Any]]:
    """
    Perform a Google Custom Search for the given query.
    Returns a list of search results with titles, snippets, and URLs.
    """
    try:
        # Build the service
        service = build("customsearch", "v1", developerKey=api_key)
        
        # Perform the search with Catholic/religious focus
        search_query = f"{query} Catholic saint feast tradition"
        
        # Execute the search using the correct API method
        result = service.cse().list(
            q=search_query,
            cx=cse_id,
            num=5,  # Get top 5 results
            safe="active",  # Safe search
            lr="lang_en"  # English language
        ).execute()
        
        # Extract and return the search results
        items = result.get("items", [])
        return [
            {
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "link": item.get("link", ""),
                "displayLink": item.get("displayLink", "")
            }
            for item in items
        ]
        
    except HttpError as e:
        print(f"Google Search API error: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error in Google Search: {e}")
        return []


def _synthesize_search_results(query: str, search_results: List[Dict[str, Any]]) -> str:
    """
    Use AI to synthesize and summarize Google search results into a coherent summary.
    """
    if not search_results:
        return _fallback_ai_research([query])[0]["summary"]
    
    client = get_ai_client()
    
    # Prepare the search results for AI processing
    search_data = {
        "query": query,
        "results": search_results
    }
    
    prompt = (
        f"You are researching information for a Catholic podcast about saints and feasts. "
        f"Based on the following Google search results for the query '{query}', "
        f"create a concise, factual, and engaging summary that would be useful for podcast hosts. "
        f"Focus on:\n"
        f"- Historical facts and context\n"
        f"- Interesting traditions or customs\n"
        f"- Spiritual significance\n"
        f"- Any dramatic or inspiring stories\n"
        f"- Cultural or liturgical connections\n\n"
        f"Write in a warm, accessible tone suitable for family listening. "
        f"Keep it under 200 words and make it engaging for podcast content.\n\n"
        f"Search results:\n{json.dumps(search_data, indent=2)}"
    )
    
    try:
        if AI_MODEL_PROVIDER == 'anthropic':
            response = client.messages.create(
                model=get_model_name(),
                max_tokens=1000,
                messages=[
                    {"role": "user", "content": f"You are a knowledgeable Catholic researcher and podcast content creator.\n\n{prompt}"}
                ]
            )
            return response.content[0].text.strip()
        else:
            response = client.chat.completions.create(
                model=get_model_name(),
                messages=[
                    {"role": "system", "content": "You are a knowledgeable Catholic researcher and podcast content creator."},
                    {"role": "user", "content": prompt}
                ],
            )
            
            return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"Error synthesizing search results: {e}")
        # Fallback: combine snippets manually
        snippets = [result.get("snippet", "") for result in search_results[:3]]
        return f"Research on {query}: {' '.join(snippets)}"


def _fallback_ai_research(queries: List[str]) -> List[Dict[str, str]]:
    """
    Fallback method using AI-only research when Google Search is unavailable.
    """
    client = get_ai_client()
    results = []
    
    for query in queries:
        try:
            prompt = (
                f"Research the following topic for a Catholic podcast about saints and feasts: {query}\n\n"
                f"Provide a concise, factual, and engaging summary (under 200 words) that includes:\n"
                f"- Historical context and facts\n"
                f"- Spiritual significance\n"
                f"- Interesting traditions or customs\n"
                f"- Any inspiring stories or legends\n"
                f"Write in a warm, accessible tone suitable for family listening."
            )
            
            if AI_MODEL_PROVIDER == 'anthropic':
                response = client.messages.create(
                    model=get_model_name(),
                    max_tokens=1000,
                    messages=[
                        {"role": "user", "content": f"You are a knowledgeable Catholic researcher and podcast content creator.\n\n{prompt}"}
                    ]
                )
                summary = response.content[0].text.strip()
            else:
                response = client.chat.completions.create(
                    model=get_model_name(),
                    messages=[
                        {"role": "system", "content": "You are a knowledgeable Catholic researcher and podcast content creator."},
                        {"role": "user", "content": prompt}
                    ],
                )
                summary = response.choices[0].message.content.strip()
            
            results.append({
                "query": query,
                "summary": summary,
                "sources": []
            })
            
        except Exception as e:
            print(f"Error in AI fallback research for '{query}': {e}")
            results.append({
                "query": query,
                "summary": f"Research summary for: {query}",
                "sources": []
            })
    
    return results


def get_structured_bio_summary(bios: List[Dict[str, Any]], search_results: List[Dict[str, str]]) -> List[StructuredBioModel]:
    print("[START] get_structured_bio_summary")
    client = get_ai_client()
    prompt = (
        "Given the following hagiographies and supplemental search information, prepare a structured summary for each saint or feast. "
        "Return only a JSON object with a 'feasts' key containing an array of objects. "
        "Each feast object must include these EXACT keys (do not rename or omit them): "
        "'Title' (string: saint/feast name), "
        "'Calendars' (array of strings: which calendar systems this appears in), "
        "'Summary' (string: brief biography and significance), "
        "'Themes' (array of strings: key spiritual themes), "
        "'CommemorationIdeas' (array of strings: ways to commemorate), "
        "'DiscussionQuestion' (string: thought-provoking question for families), "
        "'Traditions' (array of strings: associated traditions, can be empty). "
        "Use valid JSON only."
    )

    merged_data = {"biographies": bios, "search_summaries": search_results}
    result = create_structured_completion(
        client=client,
        model=get_model_name(),
        messages=[
            {"role": "system", "content": "You are a podcast script writer."},
            {"role": "user", "content": prompt + "\n" + json.dumps(merged_data)}
        ],
        response_format_model=StructuredResponse
    )

    print("[DEBUG] AI response result:")
    # print(result)
    print("[END] get_structured_bio_summary")
    return result.feasts


def generate_podcast_script(structured_bios: List[StructuredBioModel], target_date: date, original_bios: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    print("[START] generate_podcast_script")
    client = get_ai_client()
    date_str = target_date.strftime('%B %d, %Y')
    
    prompt = (
        f"You are creating an exciting and engaging Catholic podcast script for kids called 'Saintly Adventures' for {date_str}.\n"
        "This is a children's podcast that should be WARM, DRAMATIC, and INSPIRING - perfect for young listeners who love adventure stories!\n"
        "\n"
        "PODCAST STRUCTURE:\n"
        "1. WARM NARRATOR INTRODUCTION (about 30 seconds): A friendly narrator gives a brief, engaging biography of the saint\n"
        "2. AUDIO DRAMA: An exciting dramatic retelling of the most interesting legend or story from the saint's life\n"
        "3. If there are multiple feasts on this day, choose the MOST INTERESTING one, prioritizing:\n"
        "   - Current Catholic calendar first\n"
        "   - Anglican Ordinariate as final fallback\n"
        "   - Traditional calendars (1954, 1960) as final fallback\n"   
        "\n"
        "Pick only one story from the list of stories provided in the search results. If there are multiple stories, pick the most interesting one."
        "STORYTELLING STYLE:\n"
        "- Make it DRAMATIC and EXCITING - like an adventure story!\n"
        "- Emphasize HEROISM, VIRTUE, CHARITY, and other Christian values\n"
        "- Use vivid descriptions that kids can picture in their minds\n"
        "- Include moments of suspense, wonder, and triumph\n"
        "- Make the saints feel like real heroes that kids can look up to\n"
        "- Use age-appropriate language but don't talk down to children\n"
        "\n"
        "CHARACTER DEVELOPMENT:\n"
        "- Create distinct, memorable characters with clear voices\n"
        "- The saint should be the hero of the story\n"
        "- Include supporting characters that add to the drama\n"
        "- Each character should have a clear purpose in the story\n"
        "\n"
        "DRAMATIC ELEMENTS:\n"
        "- Build tension and excitement throughout the story\n"
        "- Include moments of danger, challenge, or difficulty\n"
        "- Show how the saint overcomes obstacles through faith and virtue\n"
        "- End with a satisfying resolution that reinforces the moral lesson\n"
        "\n"
        "VOICE INSTRUCTIONS:\n"
        "Include ElevenLabs-compatible voice instructions in square brackets:\n"
        "- [warmly] for the narrator's friendly introduction\n"
        "- [excitedly] for dramatic moments\n"
        "- [softly] for tender or sacred moments\n"
        "- [dramatically] for high-stakes scenes\n"
        "- [with wonder] for amazing miracles or discoveries\n"
        "- [cheerfully] for happy endings\n"
        "- [mysteriously] for suspenseful moments\n"
        "- [heroically] for the saint's brave actions\n"
        "\n"
        "IMPORTANT GUIDELINES:\n"
        "- Keep the total podcast AT LEAST 5 minutes but typically under 10 minutes for kids' attention spans\n"
        "- Make every moment engaging - no boring parts!\n"
        "- Focus on action and adventure rather than just facts\n"
        "- Emphasize the saint's courage, kindness, and faith\n"
        "- Use simple but vivid language that creates mental pictures\n"
        "- Include a clear moral lesson that's easy for kids to understand\n"
        "- Never mention podcast format or show notes - keep it immersive\n"
        "- Do not use cliche phrases, such as 'Picture this' or 'Imagine this'\n"
        "- You may absolutely consult the web search tool if supplmental information is need to make sure it is at least 5 minutes long\n"
        "\n"
        "Available ElevenLabs voices (id, descriptors, gender):\n"
        "- 7tRwuZTD1EWi6nydVerp: ['Main Blurb Narrator'] (male) ALWAYS and only use this for the intro blurb\n"
        "- cfc7wVYq4gw4OpcEEAom: ['Main Story Narrator'] (female) ALWAYS and only use this for the narrator in the story\n"
        "- vfaqCOvlrKi4Zp7C2IAm: ['Evil','Demonic','Creepy'] (male)\n"
        "- yjJ45q8TVCrtMhEKurxY: ['Mad Scientist', 'Quirky'] (male)\n"
        "- oR4uRy4fHDUGGISL0Rev: ['Wise', 'Wizard', 'Merlin', 'Magic'] (male)\n"
        "- PPzYpIqttlTYA83688JI: ['Pirate', 'Adventerous'] (male)\n"
        "- ZF6FPAbjXT4488VcRRnw: ['Young', 'British', 'Bookworm'] (female)\n"
        "- y2Y5MeVPm6ZQXK64WUui: ['Old', 'Storyteller', 'Wise'] (male)\n"
        "- Wu86LpENEn32PwtU2hv1: ['Deeper', 'Cheery'] (female)\n"
        "- FUfBrNit0NNZAwb58KWH: ['Generic', 'Main Character'] (female)\n"
        "- EkK5I93UQWFDigLMpZcX: ['Deep', 'Main Character','Narrator'] (male)\n"
        "- qBDvhofpxp92JgXJxDjB: ['Female', 'calming', 'youthful'] (female)\n"
        "- c7XGL37TTXR5zdorzHX9: ['Gossipy', 'Sassy', 'Teenager'] (female)\n"
        "- 3vk47KpWZzIrWkdEhumS: ['Chatty', 'Laid back'] (male)\n"
        "- b3tuFWghbXYRa9Cs9MJf: ['Narrator', 'Deep'] (male)\n"
        "- 0TfZ4rvne3QI7UjDxVkM: ['Childlike', 'High pitched'] (female)\n"
        "\n"
        "Assign one voice_id from the list above to each character you create based on suitability. Include a narrator.\n"
        "\n"
        "Return a JSON object with:\n"
        "- 'title': An exciting title for the episode\n"
        "- 'saint_name': The name of the saint or feast being featured\n"
        "- 'characters': A list of character names that will appear in the story\n"
        "- 'script_lines': A list of objects with 'character' (who's speaking) and 'text' (what they say)\n"
        "- 'voices': A list of { character, voice_id } objects, assigning each character an ElevenLabs 'voice_id' from the list above\n"
        "\n"
        "CRITICAL: Every 'character' name in 'script_lines' MUST exactly match a name from the 'characters' list. "
        "Do not use character names like 'Everyone', 'All', 'Crowd', or 'Chorus' unless they are explicitly listed in 'characters'. "
        "If multiple characters speak together, either list them individually or create a specific character name like 'Villagers' and include it in the characters list.\n"
        "\n"
        "Make this an adventure story that kids will want to listen to again and again!"
    )

    # Prepare the data payload
    data_payload = {
        "structured_summaries": [s.model_dump() for s in structured_bios]
    }
    
    # Add original biography data if provided
    if original_bios:
        data_payload["original_biography_data"] = original_bios
        

    result = create_structured_completion(
        client=client,
        model=get_model_name(),
        messages=[
            {"role": "system", "content": "You are a creative and passionate podcast scriptwriter who specializes in making Catholic content exciting and engaging."},
            {"role": "user", "content": prompt + "\n\nDATA:\n" + json.dumps(data_payload)}
        ],
        response_format_model=KidsPodcastScriptModel
    )
    print("[END] generate_podcast_script")
    return result.model_dump()


def clean_text_for_tts(text: str) -> str:
    """
    Clean text by removing voice instruction brackets like [laughs], [softly], etc.
    ElevenLabs TTS reads these literally, so we need to remove them.
    """
    import re
    # Remove all content within square brackets
    cleaned_text = re.sub(r'\[.*?\]', '', text)
    
    # Remove standalone "Pause" or "pause" words that might appear
    cleaned_text = re.sub(r'\b[Pp]ause\b', '', cleaned_text)
    
    # Remove other common TTS artifacts
    cleaned_text = re.sub(r'\b[Bb]reak\b', '', cleaned_text)
    cleaned_text = re.sub(r'\b[Ss]ilence\b', '', cleaned_text)
    
    # Clean up any multiple spaces that might result
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
    return cleaned_text.strip()


def extract_voice_settings(text: str) -> Dict[str, Any]:
    """
    Extract voice instruction settings from text to apply appropriate TTS parameters.
    Enhanced for more excitement and dramatic delivery.
    Returns a dictionary with voice settings that can be used to modify TTS generation.
    """
    import re
    
    # Find all voice instructions in the text
    instructions = re.findall(r'\[(.*?)\]', text.lower())
    
    # Balanced default settings for clear, natural delivery
    voice_settings = {
        "stability": 0.75,  # Higher stability for clearer speech
        "similarity_boost": 0.85,  # High clarity
        "style": 0.15,  # Moderate style variation
        "use_speaker_boost": True,
        "speed": 1.0  # Normal speed
    }
    
    # Adjust settings based on instructions with more balanced ranges
    for instruction in instructions:
        if 'softly' in instruction or 'gently' in instruction:
            voice_settings["stability"] = 0.85
            voice_settings["style"] = 0.1
            voice_settings["speed"] = 0.95
        elif 'dramatically' in instruction or 'passionately' in instruction:
            voice_settings["stability"] = 0.65
            voice_settings["style"] = 0.25
            voice_settings["speed"] = 1.05
        elif 'excitedly' in instruction or 'enthusiastically' in instruction:
            voice_settings["stability"] = 0.7
            voice_settings["style"] = 0.2
            voice_settings["speed"] = 1.05
        elif 'building excitement' in instruction or 'with growing excitement' in instruction:
            voice_settings["stability"] = 0.65
            voice_settings["style"] = 0.3
            voice_settings["speed"] = 1.1
        elif 'breathlessly' in instruction or 'in wonder' in instruction:
            voice_settings["stability"] = 0.7
            voice_settings["style"] = 0.2
            voice_settings["speed"] = 1.0
        elif 'joyfully' in instruction or 'with awe' in instruction:
            voice_settings["stability"] = 0.75
            voice_settings["style"] = 0.18
            voice_settings["speed"] = 1.02
        elif 'thoughtfully' in instruction or 'warmly' in instruction:
            voice_settings["stability"] = 0.8
            voice_settings["style"] = 0.1
            voice_settings["speed"] = 0.98
        elif 'laughs' in instruction:
            voice_settings["stability"] = 0.7
            voice_settings["style"] = 0.2
            voice_settings["speed"] = 1.05
    
    return voice_settings


def generate_tts_and_merge_with_voice_map(script: List[Dict[str, Any]], target_date: date, voice_map: Dict[str, str]) -> str:
    """
    Generate TTS audio for the script and merge into a single mp3 file for the given date.
    Includes intro music with fade-in to dialogue and outro music with fade-out from dialogue.
    Balanced audio levels for clear, natural delivery without distortion.
    target_date must be a datetime.date object.
    """
    print("[START] generate_tts_and_merge_with_voice_map")
    if not isinstance(target_date, date):
        raise TypeError(f"target_date must be a datetime.date, not {type(target_date)}")

    # Initialize ElevenLabs client
    api_key = os.getenv('ELEVEN_LABS_API_KEY')
    if not api_key:
        raise ValueError("ELEVEN_LABS_API_KEY environment variable is required")
    
    client = ElevenLabs(api_key=api_key)
    
    # Balanced voice configuration for clear audio without distortion
    voice_config = {}
    
    temp_dir = tempfile.mkdtemp()
    audio_files = []

    # If script is in kids JSON structure, normalize to a list of lines with speaker+text
    normalized_lines = []
    if isinstance(script, dict) and "script_lines" in script:
        normalized_lines = script["script_lines"]
    else:
        normalized_lines = script

    for idx, line in enumerate(normalized_lines):
        host_name = line.get("character") or line.get("PodcastHostName")
        if host_name not in voice_map:
            raise KeyError(f"No voice_id provided by AI for character: {host_name}")
        voice_id = voice_map[host_name]
        
        # Clean the text and extract voice settings
        original_text = line.get("text") or line.get("Content") or ""
        cleaned_text = clean_text_for_tts(original_text)
        voice_settings = extract_voice_settings(original_text)
        
        try:
            # Generate audio using ElevenLabs Turbo v2.5 model
            audio_response = client.text_to_speech.convert(
                text=cleaned_text,  # Use cleaned text without brackets
                voice_id=voice_id,
                model_id="eleven_turbo_v2_5",  # Use stable Turbo v2.5 model
                output_format="mp3_44100_128",  # High quality MP3
                voice_settings=voice_settings  # Apply extracted voice settings
            )

            temp_path = os.path.join(temp_dir, f"line_{idx}.mp3")
            with open(temp_path, "wb") as f:
                for chunk in audio_response:
                    if chunk:
                        f.write(chunk)
            
            # Apply gentle volume normalization to prevent distortion
            balanced_path = os.path.join(temp_dir, f"balanced_{idx}.mp3")
            subprocess.run([
                "ffmpeg", "-y", "-i", temp_path,
                "-filter_complex", "volume=1.0,loudnorm=I=-16:LRA=11:TP=-1.5",
                "-c:a", "libmp3lame", balanced_path
            ], capture_output=True, check=True)
            
            audio_files.append(balanced_path)
            
        except Exception as e:
            print(f"Error generating TTS for line {idx}: {e}")
            # Continue with other lines if one fails
            continue

    if not audio_files:
        raise RuntimeError("No audio files were generated successfully")

    # Generate output filename
    filename = generate_podcast_filename(target_date)
    podcasts_dir = "podcasts/"

    merged_path = os.path.join(temp_dir, filename)
    
    # Add natural pauses between different speakers
    enhanced_audio_files = []
    current_speaker = None
    
    for i, audio_file in enumerate(audio_files):
        # Determine speaker for this segment
        if i < len(normalized_lines):
            speaker = normalized_lines[i].get("character") or normalized_lines[i].get("PodcastHostName")
        else:
            speaker = current_speaker
            
        # Add pause if speaker changed (but not for the first segment)
        if i > 0 and current_speaker != speaker:
            # Create a natural pause
            pause_file = os.path.join(temp_dir, f"pause_{i}.mp3")
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "anoisesrc=duration=0.5:colour=white:seed=42:amplitude=0.001",
                "-filter_complex", "volume=0.01",  # Very quiet room tone
                "-c:a", "libmp3lame", pause_file
            ], capture_output=True, check=True)
            enhanced_audio_files.append(pause_file)
        
        enhanced_audio_files.append(audio_file)
        current_speaker = speaker
    
    # Get intro and outro music file paths
    intro_music_path = os.path.join(settings.MEDIA_ROOT, "podcast_assets", "saintly_adventures_theme.mp3")
    outro_music_path = os.path.join(settings.MEDIA_ROOT, "podcast_assets", "saintly_adventures_theme.mp3")
    
    # Check if intro and outro files exist
    if not os.path.exists(intro_music_path):
        print(f"Warning: Intro music not found at {intro_music_path}")
        intro_music_path = None
    if not os.path.exists(outro_music_path):
        print(f"Warning: Outro music not found at {outro_music_path}")
        outro_music_path = None
    
    # First, concatenate the dialogue audio
    dialogue_path = os.path.join(temp_dir, "dialogue.mp3")
    subprocess.run(["ffmpeg", "-y"] + sum([["-i", f] for f in enhanced_audio_files], []) + [
        "-filter_complex",
        f"concat=n={len(enhanced_audio_files)}:v=0:a=1[dialogue]",
        "-map", "[dialogue]",
        "-c:a", "libmp3lame",
        "-b:a", "128k",
        dialogue_path
    ], capture_output=True, check=True)
    
    # Helper function to get audio duration
    def get_audio_duration(file_path):
        try:
            result = subprocess.run([
                "ffprobe", "-v", "quiet", "-show_entries", 
                "format=duration", "-of", "csv=p=0", file_path
            ], capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except:
            return 10.0  # fallback duration
    
    # Build the final merge command with intro/outro if available
    if intro_music_path and outro_music_path:
        # Get durations for fade calculations
        intro_duration = get_audio_duration(intro_music_path)
        outro_duration = get_audio_duration(outro_music_path)
        intro_fade_start = max(0, intro_duration - 2)  # Start fade 2 seconds before end
        outro_fade_start = max(0, outro_duration - 2)  # Start fade 2 seconds before end
        
        # Full intro + dialogue + outro with subtle end fades
        subprocess.run([
            "ffmpeg", "-y",
            "-i", intro_music_path,     # Input 0: intro music
            "-i", dialogue_path,        # Input 1: dialogue
            "-i", outro_music_path,     # Input 2: outro music
            "-filter_complex",
            # Apply fade out only at the very end of intro music (last 2 seconds)
            f"[0:a]afade=t=out:st={intro_fade_start}:d=2[intro_faded];"
            # Apply fade out only at the very end of outro music (last 2 seconds)  
            f"[2:a]afade=t=out:st={outro_fade_start}:d=2[outro_faded];"
            # Concatenate intro + dialogue + outro
            "[intro_faded][1:a][outro_faded]concat=n=3:v=0:a=1[mixed];"
            "[mixed]loudnorm=I=-16:LRA=11:TP=-1.5[final]",
            "-map", "[final]",
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            merged_path
        ], capture_output=True, check=True)
    elif intro_music_path:
        # Get duration for fade calculation
        intro_duration = get_audio_duration(intro_music_path)
        intro_fade_start = max(0, intro_duration - 2)  # Start fade 2 seconds before end
        
        # Only intro music available with subtle end fade
        subprocess.run([
            "ffmpeg", "-y",
            "-i", intro_music_path,     # Input 0: intro music
            "-i", dialogue_path,        # Input 1: dialogue
            "-filter_complex",
            # Apply fade out only at the very end of intro music (last 2 seconds)
            f"[0:a]afade=t=out:st={intro_fade_start}:d=2[intro_faded];"
            # Concatenate
            "[intro_faded][1:a]concat=n=2:v=0:a=1[mixed];"
            "[mixed]loudnorm=I=-16:LRA=11:TP=-1.5[final]",
            "-map", "[final]",
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            merged_path
        ], capture_output=True, check=True)
    elif outro_music_path:
        # Get duration for fade calculation
        outro_duration = get_audio_duration(outro_music_path)
        outro_fade_start = max(0, outro_duration - 2)  # Start fade 2 seconds before end
        
        # Only outro music available with subtle end fade
        subprocess.run([
            "ffmpeg", "-y",
            "-i", dialogue_path,        # Input 0: dialogue
            "-i", outro_music_path,     # Input 1: outro music
            "-filter_complex",
            # Apply fade out only at the very end of outro music (last 2 seconds)
            f"[1:a]afade=t=out:st={outro_fade_start}:d=2[outro_faded];"
            # Concatenate
            "[0:a][outro_faded]concat=n=2:v=0:a=1[mixed];"
            "[mixed]loudnorm=I=-16:LRA=11:TP=-1.5[final]",
            "-map", "[final]",
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            merged_path
        ], capture_output=True, check=True)
    else:
        # No intro/outro music available, just process dialogue
        subprocess.run([
            "ffmpeg", "-y",
            "-i", dialogue_path,
            "-filter_complex",
            "[0:a]loudnorm=I=-16:LRA=11:TP=-1.5[final]",
            "-map", "[final]",
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            merged_path
        ], capture_output=True, check=True)

    with open(merged_path, "rb") as f:
        default_storage.save(os.path.join(podcasts_dir, filename), ContentFile(f.read()))

    print("[END] generate_tts_and_merge_with_voice_map")
    return os.path.join(podcasts_dir, filename)


def generate_episode_metadata(structured, script, target_date, audio_path):
    """
    Generate all metadata fields for a PodcastEpisode from structured bios, script, date, and audio path.
    Uses OpenAI to generate a cleaned-up, deduplicated, and nicely formatted episode title from the list of saint/feast names, as well as subtitle, short description, and long description.
    Returns a dict with all fields needed for PodcastEpisode.
    """
    client = get_ai_client()
    import json as _json
    episode_names = [s.Title for s in structured]
    date_str = target_date.strftime("%Y-%m-%d")
    pretty_date = target_date.strftime("%B %d, %Y")
    day_url = f"https://saints.benlocher.com/day/{date_str}/?calendar=current"
    # Prepare context for OpenAI
    context = {
        "date": pretty_date,
        "saints_and_feasts": episode_names,
        "script": script,
        "day_url": day_url
    }
    # --- Generate cleaned-up, deduplicated episode title ---
    try:
        title_prompt = (
            "Given this list of saint and feast names, return a single string suitable for use as a podcast episode title. "
            "Remove duplicates, and format the list with commas and 'and' before the last item. Do not add anything else. "
            "List: " + _json.dumps(episode_names)
        )
        if AI_MODEL_PROVIDER == 'anthropic':
            title_response = client.messages.create(
                model=get_model_name(),
                max_tokens=100,
                messages=[
                    {"role": "user", "content": f"You are a helpful assistant.\n\n{title_prompt}"}
                ]
            )
            ai_title = title_response.content[0].text.strip()
        else:
            title_response = client.chat.completions.create(
                model=get_model_name(),
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": title_prompt}
                ],
                response_format={"type": "text"}
            )
            ai_title = title_response.choices[0].message.content.strip()
        # Remove any leading/trailing quotes if present
        if ai_title.startswith('"') and ai_title.endswith('"'):
            ai_title = ai_title[1:-1]
        episode_name = f"{pretty_date}: {ai_title}"
    except Exception:
        episode_name = f"{pretty_date}: {', '.join(episode_names)}"
    # --- Generate subtitle, short description, long description ---
    try:
        prompt = (
            "Given the following context for a Catholic podcast episode, generate:\n"
            "1. A captivating subtitle (max 100 chars)\n"
            "2. A very brief, plain text short description (max 200 chars, suitable for podcast feeds\n"
            "3. A long description (for <content:encoded>, suitable for RSS, HTML allowed, must start with the provided link, and include links to referenced items or further reading if present)\n"
            "Return only a JSON object with keys: subtitle, short_description, long_description.\n"
            "Be creative, engaging, and family-friendly.\n"
            f"\nCONTEXT:\n{_json.dumps(context)}"
        )
        if AI_MODEL_PROVIDER == 'anthropic':
            response = client.messages.create(
                model=get_model_name(),
                max_tokens=1000,
                messages=[
                    {"role": "user", "content": f"You are a creative Catholic podcast producer.\n\n{prompt}"}
                ]
            )
            ai_result = response.content[0].text
        else:
            response = client.chat.completions.create(
                model=get_model_name(),
                messages=[
                    {"role": "system", "content": "You are a creative Catholic podcast producer."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            ai_result = response.choices[0].message.content
        if isinstance(ai_result, str):
            ai_result = _json.loads(ai_result)
        subtitle = ai_result.get("subtitle")
        short_desc = ai_result.get("short_description")
        long_desc = ai_result.get("long_description")
    except Exception as e:
        # Fallback to previous logic if OpenAI fails
        subtitle = structured[0].Summary if structured and hasattr(structured[0], 'Summary') else episode_name
        short_desc = f"For more, see {day_url}. "
        if structured and hasattr(structured[0], 'Summary'):
            short_desc += structured[0].Summary.split(". ")[0] + "."
        else:
            short_desc += episode_name
        long_desc = f"For more, see {day_url}.\n\n"
        for s in structured:
            long_desc += f"<b>{s.Title}</b>\n{s.Summary}\n"
            long_desc += "\n\n"
    # Build full text for metadata from script structure
    full_text = ""
    if isinstance(script, dict) and "script_lines" in script:
        try:
            full_text = "\n".join([f"{l.get('character', '')}: {l.get('text', '')}" for l in script["script_lines"]])
        except Exception:
            full_text = "\n".join([l.get("text", "") for l in script.get("script_lines", [])])
    else:
        try:
            full_text = "\n".join([line.get("Content") or line.get("text") or "" for line in script])
        except Exception:
            full_text = ""
    slug_base = f"{date_str}-{episode_names[0] if episode_names else 'episode'}"
    slug = slugify(slug_base)[:50]
    orig_slug = slug
    i = 1
    while PodcastEpisode.objects.filter(slug=slug).exists():
        slug = f"{orig_slug}-{i}"
        i += 1
    file_name = audio_path.split("/")[-1]
    from django.conf import settings
    url = settings.MEDIA_URL + audio_path if hasattr(settings, 'MEDIA_URL') else audio_path
    return {
        "slug": slug,
        "date": target_date,
        "file_name": file_name,
        "episode_title": episode_name,
        "episode_subtitle": subtitle,
        "episode_short_description": short_desc,
        "episode_long_description": long_desc,
        "episode_full_text": full_text,
    }
    
def create_publish_date(publish_date: datetime.datetime = None):
    """
    Create a publish date for a podcast episode.
    Starts with the publish_date passed, or if none, timezone.now(),
    then changes the time to 5 PM Eastern time (respecting DST if appropriate),
    then sets it as a UTC timezone, adjusting time.
    """
    from zoneinfo import ZoneInfo
    
    # Start with the provided date or current time
    if publish_date:
        # If publish_date is naive, make it timezone-aware
        if timezone.is_naive(publish_date):
            publish_date = make_aware(publish_date)
        base_datetime = publish_date
    else:
        base_datetime = timezone.now()
    
    # Get Eastern timezone (handles DST automatically)
    eastern_tz = ZoneInfo('America/New_York')
    
    # Convert to Eastern time
    eastern_time = base_datetime.astimezone(eastern_tz)
    
    # Set the time to 5 PM Eastern
    eastern_5pm = eastern_time.replace(hour=17, minute=0, second=0, microsecond=0)
    
    # Convert back to UTC
    utc_datetime = eastern_5pm.astimezone(ZoneInfo('UTC'))
    
    return utc_datetime

def create_podcast_episode(metadata, publish_date: datetime.datetime = None):
    """
    Find the most recent Podcast with religion='catholic' and create a PodcastEpisode with the given metadata.
    """
    from mutagen.mp3 import MP3
    import os
    podcast = Podcast.objects.filter(religion="catholic").order_by("-created").first()
    # Determine episode_number
    last_episode = PodcastEpisode.objects.filter(podcast=podcast).order_by("-episode_number").first()
    episode_number = (last_episode.episode_number or 0) + 1 if last_episode and last_episode.episode_number else 1
    # Determine duration
    audio_path = metadata.get("file_name")
    duration = None
    if audio_path:
        # Try to find the file in the media storage
        from django.conf import settings
        media_path = os.path.join(settings.MEDIA_ROOT, "podcasts", audio_path)
        if os.path.exists(media_path):
            try:
                audio = MP3(media_path)
                duration = int(audio.info.length)
            except Exception:
                duration = None
    
    # Create the publish date
    final_publish_date = create_publish_date(publish_date)
    
    PodcastEpisode.objects.create(
        slug=metadata["slug"],
        date=metadata["date"],
        podcast=podcast,
        file_name=metadata["file_name"],
        episode_title=metadata["episode_title"],
        episode_subtitle=metadata["episode_subtitle"],
        episode_short_description=metadata["episode_short_description"],
        episode_long_description=metadata["episode_long_description"],
        episode_full_text=metadata["episode_full_text"],
        duration=duration,
        episode_number=episode_number,
        published_date=final_publish_date,
    )


def create_full_podcast(target_date: date, publish_date: datetime.datetime = None) -> str:
    """
    Create a full podcast for the given date. target_date must be a datetime.date object.
    """
    print("[START] create_full_podcast")
    if not isinstance(target_date, date):
        raise TypeError(f"target_date must be a datetime.date, not {type(target_date)}")
    bios = get_biographies_for_day(target_date)
    research_queries = identify_research_queries(bios)
    search_results = supplement_with_searches(research_queries)
    structured = get_structured_bio_summary(bios, search_results)
    script = generate_podcast_script(structured, target_date, bios)  # Pass original bios
    print(script)
    # Require AI-assigned voice map; no local fallback
    voice_map = {}
    if isinstance(script, dict) and script.get("voices"):
        raw_voices = script.get("voices")
        if isinstance(raw_voices, list):
            voice_map = {item.get("character"): item.get("voice_id") for item in raw_voices if item.get("character") and item.get("voice_id")}
        else:
            voice_map = raw_voices
    else:
        raise ValueError("AI response did not include required 'voices' assignments")
   
    print("[INFO] Assigned voice IDs:", voice_map)
    result = generate_tts_and_merge_with_voice_map(script, target_date, voice_map)

    # Generate metadata and create PodcastEpisode
    metadata = generate_episode_metadata(structured, script, target_date, result)
    create_podcast_episode(metadata, publish_date)

    print("[END] create_full_podcast")
    return result


def generate_next_day_podcast() -> str:
    """
    Generate a podcast for tomorrow and set it to publish today at 5 PM.
    Returns the audio file path of the generated podcast.
    """
    print("[START] generate_next_day_podcast")
    
    # Get tomorrow's date in Eastern time
    from zoneinfo import ZoneInfo
    eastern_tz = ZoneInfo('America/New_York')
    eastern_now = timezone.now().astimezone(eastern_tz)
    tomorrow = eastern_now.date() + datetime.timedelta(days=1)
    
    if PodcastEpisode.objects.filter(date=tomorrow).exists():
        print(f"[INFO] Podcast for {tomorrow} already exists, skipping generation")
        return None
    
    # Set publish date to today at 5 PM (by passing None, create_publish_date will use current time)
    today_5pm = create_publish_date(None)
    
    print(f"Generating podcast for {tomorrow} to publish at {today_5pm}")
    
    try:
        result = create_full_podcast(tomorrow, today_5pm)
        print(f"[SUCCESS] Generated podcast for {tomorrow}: {result}")
        return result
    except Exception as e:
        print(f"[ERROR] Failed to generate podcast for {tomorrow}: {e}")
        raise
    
    print("[END] generate_next_day_podcast")

