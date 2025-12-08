from datetime import date
import datetime
from typing import Optional

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
KIDS_IDENTIFY_QUERIES_PROMPT = (
    "You are preparing a podcast targeted at kids aged 4-16 about today's Catholic saints and feasts that gives a short biography followed by a dramatic audio drama of a story or legend from the life of the saint or related to the feast. Based on the following data, identify 1–4 factual questions a good host might research to make the show more informative, interesting, or engaging, focusing on colecting dramatic stories. Return only a JSON object with a 'queries' key containing a list of strings."
)

KIDS_STRUCTURED_BIO_PROMPT = (
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
    "'Legends' (array of strings: detailed legends or stories about the saint or feast, showcasing dramatic elements and their virtues)"
    "Use valid JSON only."
)

KIDS_SCRIPT_PROMPT_TEMPLATE = """
You are creating an exciting and engaging Catholic podcast script for kids called 'Saintly Adventures' for {date}.
This is a children's podcast that should be WARM, DRAMATIC, and INSPIRING - perfect for young listeners who love adventure stories!

PODCAST STRUCTURE:
1. WARM NARRATOR INTRODUCTION (about 30 seconds): A friendly narrator gives a brief, engaging biography of the saint
2. AUDIO DRAMA: An exciting dramatic retelling of the most interesting legend or story from the saint's life
3. If there are multiple feasts on this day, choose the MOST INTERESTING one, prioritizing:
   - Current Catholic calendar first
   - Anglican Ordinariate as fallback
   - Traditional calendars (1954 then 1960) as final fallback
4. You do not need to mention the calendar in the script, just use the name of the feast.

Pick only one story from the list of stories provided in the search results. If there are multiple stories, pick the most interesting one.
STORYTELLING STYLE:
- Make it DRAMATIC and EXCITING - like an adventure story!
- Emphasize HEROISM, VIRTUE, CHARITY, and other Christian values
- Use vivid descriptions that kids can picture in their minds
- Include moments of suspense, wonder, and triumph
- Make the saints feel like real heroes that kids can look up to
- Use age-appropriate language but don't talk down to children

CHARACTER DEVELOPMENT:
- Create distinct, memorable characters with clear voices
- The saint should be the hero of the story
- Include supporting characters that add to the drama
- Each character should have a clear purpose in the story

DRAMATIC ELEMENTS:
- Build tension and excitement throughout the story
- Include moments of danger, challenge, or difficulty
- Show how the saint overcomes obstacles through faith and virtue
- End with a satisfying resolution that reinforces the moral lesson

VOICE INSTRUCTIONS:
Include ElevenLabs-compatible voice instructions in square brackets:
- [warmly] for the narrator's friendly introduction
- [excitedly] for dramatic moments
- [softly] for tender or sacred moments
- [dramatically] for high-stakes scenes
- [with wonder] for amazing miracles or discoveries
- [cheerfully] for happy endings
- [mysteriously] for suspenseful moments
- [heroically] for the saint's brave actions
- [mysteriously] for suspenseful moments
- [heroically] for the saint's brave actions
- [solemnly] for sacred moments
- Others as deemed good and appropriate

Also include sounds like [laugh] [giggles] [growls] [chimes] when appropriate

PROMPTING (v3 model guidance):
- The model interprets emotional context directly from the text. Descriptive cues like "she said excitedly" and punctuation (e.g., exclamation marks!) will influence delivery.
- Use non-speech audio tags in square brackets to shape delivery and sound design. Categories include:
  - Emotions and delivery: [sad], [laughing], [whispering]
  - Audio events: [church bells], [soft choir humming], [gentle footsteps on stone], [pages rustling], [crowd murmurs], [wind through the cloister] NOTE: Do include at least a few audio events.
  - Overall direction: [cathedral procession], [stormy night at sea], [busy market square], [quiet monastery], [royal court]
- You can signal interruptions with punctuation and tags:
  - "[cautiously] Father, may I ask a ques-"
  - "[gently interrupting] Of course. [warmly] What troubles you?"
- Ellipses can indicate trailing sentences or hesitations:
  - "[in awe] I... I think that was a miracle..."
  - "[whispering] Did you hear the [church bells]?"
  - "[elated] Yes! [laughing] Saint Francis did it again!"
Include such tags and punctuation naturally in character lines to enhance performance and immersion for kids.

IMPORTANT GUIDELINES:
- Keep the total podcast AT LEAST 4 minutes but typically under 10 minutes for kids' attention spans
- Make every moment engaging - no boring parts!
- Focus on action and adventure rather than just facts
- Emphasize the saint's courage, kindness, and faith
- Use simple but vivid language that creates mental pictures
- Include a clear moral lesson that's easy for kids to understand
- Never mention podcast format or show notes - keep it immersive
- Do not use cliche phrases, such as 'Picture this' or 'Imagine this'
- You may absolutely consult the web search tool if supplmental information is need to make sure it is at least 5 minutes long
- Spell out all ambiguous words, names, and places so they can be read as audio, for example, 'Pius X' should be spelled out as 'Pius the Tenth, so that it is clear to read.'
- This script is meant for being spoken, so write as if it were spoken umabiguosly word for word, even if it's not the way you'd write it 

Available ElevenLabs voices (id, description):
- EkK5I93UQWFDigLMpZcX: A slightly husky and bassy voice with a standard American accent. Modulated, controlled, and direct and perfect for audiobooks, captivating narrations, or storytelling, or other professional voiceover work. ALWAYS and only use this for the intro blurb
- Z3R5wn05IrDiVCyEkUrK: A young, mature female narrator with a mysterious and emotive tone, perfect for fantasy, romance, urban fantasy, and wellness. ALWAYS and only use this for the narrator in the story
- aMSt68OGf4xUZAnLpTU8: A grounded female professional, great for podcasts or ConvoAI.
- tnSpp4vdxKPjI9w0GnoV: Upbeat and clear, female
- Hjzqw9NR0xFMYU9Us0DL: A dark, brooding character voice, perfect for video games.
- BpjGufoPiobT79j2vtj4: A young female with a velvety, laid-back cadence, exuding late-night warmth and intimacy. Priyanka is the sister of Monika Sogam, one of the most beloved voices on ElevenLabs.
- kdmDKE6EkgrWrrykO9Qt: Youthful and authentic, with a conversational tone that's relatable and down-to-earth.
- 1SM7GgM6IMuvQlz2BwM3: Conversational, relaxed male voice
- ouL9IsyrSnUkCmfnD02u: Professional British character voice - high-pitched, raspy male gnome with snarky comedic timing and true emotional depth. Perfect for fantasy narration, audiobooks, and video games NPC roles.
- 5l5f8iK3YPeGga21rQIX: A conversational, feminine voice that is perfect for narration.
- scOwDtmlUjD3prqpp97I: A warm and clear middle-aged American voice. Optimized for v3. Perfect for Agents, IVR, Educational Training, and Audiobooks.
- NOpBlnGInO9m6vDvFkFC: A friendly grandpa who knows how to enthrall his audience with tall tales and fun adventures.
- BZgkqPqms7Kj9ulSkVzn: Great for v3, conversation, energetic, happy.
- yjJ45q8TVCrtMhEKurxY: Quirky mad scientist. Energetic, quirky voice ideal for eccentric characters and inventive narration.
- TX3LPaxmHKxFdv7VOQHJ: A young male adult with energy and warmth - suitable for reels and shorts.
- iP95p4xoKVk53GoZ742B: Natural and real, this down-to-earth male voice is great across many use-cases.
- SOYHLrjzK2X1ezoPC6cr: An animated male warrior ready to charge forward.
- N2lVS1w4EtoT3dr4eOWO: Deceptively gravelly, yet unsettling edge.
- FGY2WhTYpPnrIDTdsKH5: This young adult female voice delivers sunny enthusiasm with a quirky attitude.
- cgSgspJ2msm6clMCkdW9: Young and popular, this playful American female voice is perfect for trendy content.
- vfaqCOvlrKi4Zp7C2IAm: A deep demon monster. Perfect for video games, characters, and animation. Ghoul, Monster, Fantasy, Dark, Horror, Male.
- oR4uRy4fHDUGGISL0Rev: Myrddin: The definitive (800+ years old) wizard voice for true magical narration. Commanding magical authority with twinkling wisdom and warmth; perfect for audiobooks, RPGs, and mystical narration.
- PPzYpIqttlTYA83688JI: A pirate: a jovial and exuberant sea dog. Gristly Cornwall accent with extended vowels and long ARR's!

CRITICAL VOICE ASSIGNMENT RULES:
- The intro blurb MUST be voiced by EkK5I93UQWFDigLMpZcX. Do not use this voice for any other character.
- The story narrator MUST be voiced by Z3R5wn05IrDiVCyEkUrK. Do not use this voice for any other character.

Assign one voice_id from the list above to each character you create based on suitability. Include a narrator.

Return a JSON object with:
- 'title': An exciting title for the episode
- 'saint_name': The name of the saint or feast being featured
- 'characters': A list of character names that will appear in the story
- 'script_lines': A list of objects with 'character' (who's speaking) and 'text' (what they say)
- 'voices': A list of { character, voice_id } objects, assigning each character an ElevenLabs 'voice_id' from the list above

CRITICAL: Every 'character' name in 'script_lines' MUST exactly match a name from the 'characters' list. Do not use character names like 'Everyone', 'All', 'Crowd', or 'Chorus' unless they are explicitly listed in 'characters'. If multiple characters speak together, either list them individually or create a specific character name like 'Villagers' and include it in the characters list.

Make this an adventure story that kids will want to listen to again and again!
"""


def _get_generator() -> PodcastGenerator:
    return PodcastGenerator(
        GeneratorConfig(
            ai=AIConfig(provider="openai", model="gpt-5"),
            prompts=PromptsConfig(
                identify_research_queries_prompt=KIDS_IDENTIFY_QUERIES_PROMPT,
                structured_bio_prompt=KIDS_STRUCTURED_BIO_PROMPT,
                script_prompt_template=KIDS_SCRIPT_PROMPT_TEMPLATE,
            ),
            voices=VoiceConfig(
                mode="ai_assigned",
                allowed_voice_ids=[
                    "EkK5I93UQWFDigLMpZcX",
                    "Z3R5wn05IrDiVCyEkUrK",
                    "aMSt68OGf4xUZAnLpTU8",
                    "tnSpp4vdxKPjI9w0GnoV",
                    "Hjzqw9NR0xFMYU9Us0DL",
                    "BpjGufoPiobT79j2vtj4",
                    "kdmDKE6EkgrWrrykO9Qt",
                    "1SM7GgM6IMuvQlz2BwM3",
                    "ouL9IsyrSnUkCmfnD02u",
                    "5l5f8iK3YPeGga21rQIX",
                    "scOwDtmlUjD3prqpp97I",
                    "NOpBlnGInO9m6vDvFkFC",
                    "BZgkqPqms7Kj9ulSkVzn",
                    "yjJ45q8TVCrtMhEKurxY",
                    "TX3LPaxmHKxFdv7VOQHJ",
                    "iP95p4xoKVk53GoZ742B",
                    "SOYHLrjzK2X1ezoPC6cr",
                    "N2lVS1w4EtoT3dr4eOWO",
                    "FGY2WhTYpPnrIDTdsKH5",
                    "cgSgspJ2msm6clMCkdW9",
                    "vfaqCOvlrKi4Zp7C2IAm",
                    "oR4uRy4fHDUGGISL0Rev",
                    "PPzYpIqttlTYA83688JI",
                ],
            ),
            audio=AudioAssetsConfig(
                intro_filename="saintly_adventures_theme.mp3",
                outro_filename="saintly_adventures_theme.mp3",
            ),
            output=OutputConfig(filename_prefix="saintly_adventures"),
            linkage=PodcastLinkageConfig(podcast_slug="saintly_adventures"),
        )
    )


def create_full_podcast(target_date: date, publish_date: datetime.datetime = None) -> str:
    return _get_generator().create_full_podcast(target_date, publish_date)


def generate_next_day_podcast(target_date: Optional[date] = None) -> Optional[str]:
    return _get_generator().generate_next_day_podcast(target_date)


