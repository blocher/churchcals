from datetime import date
import datetime

from saints.podcast_generator import (
    PodcastGenerator,
    GeneratorConfig,
    AIConfig,
    VoiceConfig,
    AudioAssetsConfig,
    OutputConfig,
    PodcastLinkageConfig,
    PromptsConfig,
)


# Preset prompts specific to this podcast (moved from generator)
ADULT_IDENTIFY_QUERIES_PROMPT = (
    "You are preparing a podcast about today's Catholic saints and feasts. Based on the following data, identify 1–5 factual questions a good host might research to make the show more informative, interesting, or engaging. Return only a JSON object with a 'queries' key containing a list of strings."
)

ADULT_STRUCTURED_BIO_PROMPT = (
    "Given the following hagiographies and supplemental search information, write structured summaries for each feast or saint.\n"
    "Include: a summary; themes; ideas for commemoration; one thoughtful discussion question; and if appropriate, one or two dramatic or pious stories or legends that enrich the episode.\n"
    "Only include stories if they genuinely add to the spiritual and narrative interest.\n"
    "Also include a list of any traditions associated with the feast or saint.\n"
    "Return only a JSON object with a 'feasts' key. Each feast must include the following keys: 'Title', 'Calendars', 'Summary', 'Themes', 'CommemorationIdeas', 'DiscussionQuestion'. Optionally include 'Traditions'. Do not rename or omit these fields. Use valid JSON only."
)

ADULT_SCRIPT_PROMPT_TEMPLATE = """
    You are generating a warm, upbeat, and engaging Catholic podcast script for the show 'Saints and Seasons' for {date}.\n
    The podcast is modeled after NotebookLM but conversational, joyful, and well-researched.\n
    For each structured bio, create a flowing, natural dialogue between hosts Maria and John that is engaging and heartfelt.\n
    The tone should be REVERENT, INSPIRING, and CAPTIVATING—suitable for a family audience who loves engaging content.\n
    Go through the hagiography narratively and conversationally, adding reflections and tying in spiritual themes naturally.\n
    Dramatic or pious stories from the saint's life (or legends) should be told vividly and only when they add to the story.\n
    \n
    ENGAGEMENT GUIDELINES:\n
    - Create natural back-and-forth conversation between hosts\n
    - Include moments of genuine wonder and appreciation\n
    - Use thoughtful pauses for emphasis\n
    - Express sincere appreciation for the saints' stories\n
    - Build narrative momentum naturally\n
    - Use language that conveys inspiration and warmth\n
    \n
    DATA SOURCES:\n
    You have THREE sources of information:\n
    1. STRUCTURED SUMMARIES (PRIMARY): Use these as your main guide for the overall narrative, themes, and discussion flow. These summaries have been enhanced with current research from Google Search and AI analysis, providing:\n
       - Historical facts and context from current sources\n
       - Interesting traditions and customs\n
       - Spiritual significance and cultural connections\n
       - Dramatic or inspiring stories and legends\n
       - Contemporary relevance and connections\n
    2. ORIGINAL BIOGRAPHY DATA (SUPPLEMENTAL): Use this rich additional detail ONLY when it enhances the story:\n
       - Include specific quotes if they're particularly profound or illustrative\n
       - Use detailed stories from legends or hagiographies when they add drama or spiritual insight\n
       - Mention specific traditions or foods when they're interesting and relevant\n
       - Reference writings when they illuminate the saint's character or teachings\n
       - DO NOT feel compelled to use everything - be selective and purposeful\n
       - The original data is there to enrich, not overwhelm the conversation\n
    3. ENHANCED RESEARCH DATA (INTEGRATED): The structured summaries now include current research findings that provide:\n
       - Up-to-date historical information and context\n
       - Contemporary interpretations and relevance\n
       - Additional traditions and cultural connections\n
       - Recent discoveries or insights about the saints/feasts\n
       - Cross-cultural and interfaith perspectives where relevant\n
    \n
    Include quotes only if they naturally elevate the conversation.\n
    Family life, prayer, witness, and faith should be woven into the reflections with warmth and sincerity.\n
    Mention any traditions associated with the feast or saint with genuine interest.\n
    Leverage the enhanced research data to add contemporary relevance, interesting historical context, and engaging details that make the saints' stories more accessible and inspiring to modern listeners.\n
    \n
    Each episode should:\n
    - Begin with the date and the names of all commemorated saints and feasts\n
    - Calendar mentions:\n
        - Assume the current General Roman Calendar by default; do not say this explicitly.\n
        - Only mention other calendars if the feast is NOT on the current General Roman Calendar.\n
        - When needed, use these exact names: 'Traditional Roman Calendar (1954)', 'Traditional Roman Calendar (1960)', 'Anglican Ordinariate'.\n
        - If multiple non-current calendars apply, list them succinctly (e.g., 'Traditional Roman Calendar (1960) and Anglican Ordinariate').\n
        - If the feast is the same on both the 1954 and 1960 calendars,  cobine it to: 'Traditional Calendar' instead of listing both seperately.\n
    - Include 1–2 standout stories or traditions told with engaging detail.\n
    - End with a practical idea for how listeners might commemorate the day, presented warmly.\n
    \n
    Use simple, flowing dialogue with natural energy. Format clearly.\n
    Include ElevenLabs-compatible voice instructions in square brackets when appropriate to enhance delivery:\n
    - [warmly] for moments of connection and kindness\n
    - [thoughtfully] for reflective passages\n
    - [with wonder] for moments of amazement\n
    - [gently] for tender or moving stories\n
    - [appreciatively] for inspiring stories\n
    - [softly] for intimate or sacred moments\n
    - [cheerfully] for joyful moments\n
    - [earnestly] for sincere or important points\n
    - [admiringly] for remarkable achievements\n
    - [with interest] for intriguing details\n
    Use these naturally to enhance the conversational flow without overdoing it.\n
    \n
    PROMPTING (v3 model guidance):
    - The model interprets emotional context directly from the text. Descriptive cues like "he said quietly" or "she replied with warmth" and punctuation will influence delivery.
    - Use non-speech audio tags in square brackets to shape delivery and sound design. Categories include:
    - Emotions and delivery: [thoughtfully], [warmly], [reverently], [with quiet awe], [gently]
    - Audio events: [distant church bell], [soft choir], [pages turning], [footsteps in the nave], [congregation murmurs] NOTE: Make a sound when transitioning to the first saint, and between saints, and at the end, but otherwise use very sparingly if at all.
    - Overall direction: [quiet chapel], [evening vespers], [pilgrimage], [study], [procession]
    - You can signal interruptions with punctuation and tags:
        - "[gently interjecting] May I add—"
        - "[considering] That's a fair question—"
        - Ellipses can indicate trailing sentences or hesitations:
    - "[reflectively] I... find his witness challenging."
    - "[softly] Did you notice the connection to the liturgy?"
    - "[with warmth] It's moving how Saint Francis lived this so simply."
    - Include such tags and punctuation naturally in character lines to enhance performance and immersion for a mature, conversational tone.
    Important: Do not use cliche phrases, such as 'Picture this' or 'Imagine this'\n
    \n
    IMPORTANT: NEVER mention show notes, episode descriptions, or any meta-references to the podcast format. Keep the conversation natural and immersive.\n
    \n
    IMPORTANT: While the script should be natural and conversational, limit filler words and fluff. Keep it concise and to the point.\n
    \n
    IMPORTANT: The podcast should never be more than 15 minutes long (but can be shorter).\n
    IMPORTANT: - This script is meant for being spoken, so write as if it were spoken umabiguosly word for word, even if it's not the way you'd write it 
    Return only a JSON object with a 'lines' key, whose value is a list of objects with PodcastHostName, Content, and SystemInstructions.
"""


def _get_generator() -> PodcastGenerator:
    return PodcastGenerator(
        GeneratorConfig(
            ai=AIConfig(provider="openai", model="gpt-5"),
            prompts=PromptsConfig(
                identify_research_queries_prompt=ADULT_IDENTIFY_QUERIES_PROMPT,
                structured_bio_prompt=ADULT_STRUCTURED_BIO_PROMPT,
                script_prompt_template=ADULT_SCRIPT_PROMPT_TEMPLATE,
            ),
            voices=VoiceConfig(
                mode="fixed",
                fixed_voice_map={
                    "John": "gs0tAILXbY5DNrJrsM6F",
                    "Maria": "zGjIP4SZlMnY9m93k97r",
                },
            ),
            audio=AudioAssetsConfig(
                intro_filename="intro_music.mp3",
                outro_filename="outro_music.mp3",
            ),
            output=OutputConfig(filename_prefix="saints_and_seasons"),
            linkage=PodcastLinkageConfig(podcast_slug="saints_and_seasons"),
        )
    )


def create_full_podcast(target_date: date, publish_date: datetime.datetime = None) -> str:
    return _get_generator().create_full_podcast(target_date, publish_date)


def generate_next_day_podcast() -> str:
    return _get_generator().generate_next_day_podcast()


