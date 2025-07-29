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


from django_cron import CronJobBase, Schedule


# Configuration: AI Model Selection
# Set to 'openai' for GPT-4.1 or 'grok' for Grok 4
AI_MODEL_PROVIDER = 'openai'  # Options: 'openai', 'grok'

# Model configurations
MODEL_CONFIG = {
    'openai': {
        'model': 'gpt-4.1',
        'client_module': 'openai',
        'client_class': 'OpenAI'
    },
    'grok': {
        'model': 'grok-2-1212',
        'client_module': 'openai',  # Grok uses OpenAI-compatible API
        'client_class': 'OpenAI',
        'base_url': 'https://api.x.ai/v1',
        'api_key_env': 'XAI_API_KEY'
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
    else:
        raise ValueError(f"Unsupported AI model provider: {AI_MODEL_PROVIDER}")


def get_model_name():
    """
    Get the model name for the configured provider.
    """
    return MODEL_CONFIG[AI_MODEL_PROVIDER]['model']


def create_structured_completion(client, model, messages, response_format_model):
    """
    Create a structured completion that works with both OpenAI and Grok.
    For OpenAI, uses the .parse() method with Pydantic models.
    For Grok, falls back to JSON mode and manual parsing.
    """
    if AI_MODEL_PROVIDER == 'openai':
        # Use OpenAI's structured output with .parse()
        response = client.beta.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=response_format_model
        )
        return response.choices[0].message.parsed
    else:
        # Use JSON mode for Grok and manually parse
        # Update the system message to include JSON schema instructions for Grok
        enhanced_messages = messages.copy()
        if enhanced_messages and enhanced_messages[0]["role"] == "system":
            # Create a simplified schema description instead of the full JSON schema
            if hasattr(response_format_model, '__name__') and response_format_model.__name__ == 'PodcastScriptModel':
                schema_description = '{"lines": [{"PodcastHostName": "string", "Content": "string", "SystemInstructions": "string"}, ...]}'
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
from pydantic import BaseModel
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


class PodcastLineModel(BaseModel):
    PodcastHostName: str
    Content: str
    SystemInstructions: str


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
    lines: List[PodcastLineModel]


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
        "You are preparing a podcast about today's Catholic saints and feasts. Based on the following data, identify 1–10 factual questions a good host might research to make the show more informative, interesting, or engaging. Return only a JSON object with a 'queries' key containing a list of strings."
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
    print(result)
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
            print("AAA")
            print(search_results)
            # Use AI to synthesize and summarize the search results
            summary = _synthesize_search_results(query, search_results)
            print("BBB")
            print(summary)
            print("CCC")
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
    print("[END] supplement_with_searches")
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
        response = client.chat.completions.create(
            model=get_model_name(),
            messages=[
                {"role": "system", "content": "You are a knowledgeable Catholic researcher and podcast content creator."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=400,
            temperature=0.7
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
            
            response = client.chat.completions.create(
                model=get_model_name(),
                messages=[
                    {"role": "system", "content": "You are a knowledgeable Catholic researcher and podcast content creator."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
                temperature=0.7
            )
            
            results.append({
                "query": query,
                "summary": response.choices[0].message.content.strip(),
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
        "Given the following hagiographies and supplemental search information, write structured summaries for each feast or saint.\n"
        "Include: a summary; themes; ideas for commemoration; one thoughtful discussion question; and if appropriate, one or two dramatic or pious stories or legends that enrich the episode.\n"
        "Only include stories if they genuinely add to the spiritual and narrative interest.\n"
        "Also include a list of any traditions associated with the feast or saint.\n"
        "Return only a JSON object with a 'feasts' key. Each feast must include the following keys: 'Title', 'Calendars', 'Summary', 'Themes', 'CommemorationIdeas', 'DiscussionQuestion'. Optionally include 'Traditions'. Do not rename or omit these fields. Use valid JSON only."
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
    print(result)
    print("[END] get_structured_bio_summary")
    return result.feasts


def generate_podcast_script(structured_bios: List[StructuredBioModel], target_date: date, original_bios: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    print("[START] generate_podcast_script")
    client = get_ai_client()
    date_str = target_date.strftime('%B %d, %Y')
    
    prompt = (
        f"You are generating a warm, upbeat, and engaging Catholic podcast script for the show 'Saints and Seasons' for {date_str}.\n"
        "The podcast is modeled after NotebookLM but conversational, joyful, and well-researched.\n"
        "For each structured bio, create a flowing, natural dialogue between hosts Maria and John that is engaging and heartfelt.\n"
        "The tone should be REVERENT, INSPIRING, and CAPTIVATING—suitable for a family audience who loves engaging content.\n"
        "Go through the hagiography narratively and conversationally, adding reflections and tying in spiritual themes naturally.\n"
        "Dramatic or pious stories from the saint's life (or legends) should be told vividly and only when they add to the story.\n"
        "\n"
        "ENGAGEMENT GUIDELINES:\n"
        "- Create natural back-and-forth conversation between hosts\n"
        "- Include moments of genuine wonder and appreciation\n"
        "- Use thoughtful pauses for emphasis\n"
        "- Express sincere appreciation for the saints' stories\n"
        "- Build narrative momentum naturally\n"
        "- Use language that conveys inspiration and warmth\n"
        "\n"
        "DATA SOURCES:\n"
        "You have THREE sources of information:\n"
        "1. STRUCTURED SUMMARIES (PRIMARY): Use these as your main guide for the overall narrative, themes, and discussion flow. These summaries have been enhanced with current research from Google Search and AI analysis, providing:\n"
        "   - Historical facts and context from current sources\n"
        "   - Interesting traditions and customs\n"
        "   - Spiritual significance and cultural connections\n"
        "   - Dramatic or inspiring stories and legends\n"
        "   - Contemporary relevance and connections\n"
        "2. ORIGINAL BIOGRAPHY DATA (SUPPLEMENTAL): Use this rich additional detail ONLY when it enhances the story:\n"
        "   - Include specific quotes if they're particularly profound or illustrative\n"
        "   - Use detailed stories from legends or hagiographies when they add drama or spiritual insight\n"
        "   - Mention specific traditions or foods when they're interesting and relevant\n"
        "   - Reference writings when they illuminate the saint's character or teachings\n"
        "   - DO NOT feel compelled to use everything - be selective and purposeful\n"
        "   - The original data is there to enrich, not overwhelm the conversation\n"
        "3. ENHANCED RESEARCH DATA (INTEGRATED): The structured summaries now include current research findings that provide:\n"
        "   - Up-to-date historical information and context\n"
        "   - Contemporary interpretations and relevance\n"
        "   - Additional traditions and cultural connections\n"
        "   - Recent discoveries or insights about the saints/feasts\n"
        "   - Cross-cultural and interfaith perspectives where relevant\n"
        "\n"
        "Include quotes only if they naturally elevate the conversation.\n"
        "Family life, prayer, witness, and faith should be woven into the reflections with warmth and sincerity.\n"
        "Mention any traditions associated with the feast or saint with genuine interest.\n"
        "Leverage the enhanced research data to add contemporary relevance, interesting historical context, and engaging details that make the saints' stories more accessible and inspiring to modern listeners.\n"
        "\n"
        "Each episode should:\n"
        "- Begin with the date and the names of all commemorated saints and feasts\n"
        "- If the feasts appears exclusively on a calendar(s) other than the current Catholic calendar, include which calendar(s) they are on: traditional (1954), traiditonal (1960), Anglican Ordinariate\n" 
        "- Include 1–2 standout stories or traditions told with engaging detail.\n"
        "- End with a practical idea for how listeners might commemorate the day, presented warmly.\n"
        "\n"
        "Use simple, flowing dialogue with natural energy. Format clearly.\n"
        "Include ElevenLabs-compatible voice instructions in square brackets when appropriate to enhance delivery:\n"
        "- [warmly] for moments of connection and kindness\n"
        "- [thoughtfully] for reflective passages\n"
        "- [with wonder] for moments of amazement\n"
        "- [gently] for tender or moving stories\n"
        "- [appreciatively] for inspiring stories\n"
        "- [softly] for intimate or sacred moments\n"
        "- [cheerfully] for joyful moments\n"
        "- [earnestly] for sincere or important points\n"
        "- [admiringly] for remarkable achievements\n"
        "- [with interest] for intriguing details\n"
                 "Use these naturally to enhance the conversational flow without overdoing it.\n"
         "\n"
         "Important: Do not use cliche phrases, such as 'Picture this' or 'Imagine this'"
        "\n"
        "IMPORTANT: NEVER mention show notes, episode descriptions, or any meta-references to the podcast format. Keep the conversation natural and immersive.\n"
        "\n"
        "IMPORTANT: While the script should be natural and conversational, limit filler words and fluff. Keep it concise and to the point."
        "\n"
        "IMPORTANT: The podcast should never be more than 15 minutes long (but can be shorter)."
        "Return only a JSON object with a 'lines' key, whose value is a list of objects with PodcastHostName, Content, and SystemInstructions."
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
        response_format_model=PodcastScriptModel
    )
    print("[END] generate_podcast_script")
    return [line.model_dump() for line in result.lines]


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


def generate_tts_and_merge(script: List[Dict[str, Any]], target_date: date) -> str:
    """
    Generate TTS audio for the script and merge into a single mp3 file for the given date.
    Includes intro music with fade-in to dialogue and outro music with fade-out from dialogue.
    Balanced audio levels for clear, natural delivery without distortion.
    target_date must be a datetime.date object.
    """
    print("[START] generate_tts_and_merge")
    if not isinstance(target_date, date):
        raise TypeError(f"target_date must be a datetime.date, not {type(target_date)}")

    # Initialize ElevenLabs client
    api_key = os.getenv('ELEVEN_LABS_API_KEY')
    if not api_key:
        raise ValueError("ELEVEN_LABS_API_KEY environment variable is required")
    
    client = ElevenLabs(api_key=api_key)
    
    # Balanced voice configuration for clear audio without distortion
    voice_config = {
        "John": {
            "voice_id": "gs0tAILXbY5DNrJrsM6F",  # Jeff - warm male voice
            "volume_multiplier": 1.0  # Balanced volume
        },
        "Maria": {
            "voice_id": "zGjIP4SZlMnY9m93k97r",  # Eve - clear female voice  
            "volume_multiplier": 1.0  # Balanced volume
        }
    }
    
    temp_dir = tempfile.mkdtemp()
    audio_files = []

    for idx, line in enumerate(script):
        host_name = line["PodcastHostName"]
        voice_config_data = voice_config.get(host_name, voice_config["Maria"])
        voice_id = voice_config_data["voice_id"]
        volume_multiplier = voice_config_data["volume_multiplier"]
        
        # Clean the text and extract voice settings
        original_text = line["Content"]
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
        if i < len(script):
            speaker = script[i]["PodcastHostName"]
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
    intro_music_path = os.path.join(settings.MEDIA_ROOT, "podcast_assets", "intro_music.mp3")
    outro_music_path = os.path.join(settings.MEDIA_ROOT, "podcast_assets", "outro_music.mp3")
    
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

    print("[END] generate_tts_and_merge")
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
    full_text = "\n".join([line["Content"] for line in script])
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
    result = generate_tts_and_merge(script, target_date)

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

