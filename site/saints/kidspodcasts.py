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

Available ElevenLabs voices (id, descriptors, gender):
- 7tRwuZTD1EWi6nydVerp: ['Main Blurb Narrator'] (male) ALWAYS and only use this for the intro blurb
- cfc7wVYq4gw4OpcEEAom: ['Main Story Narrator'] (female) ALWAYS and only use this for the narrator in the story
- vfaqCOvlrKi4Zp7C2IAm: ['Evil','Demonic','Creepy'] (male)
- yjJ45q8TVCrtMhEKurxY: ['Mad Scientist', 'Quirky'] (male)
- oR4uRy4fHDUGGISL0Rev: ['Wise', 'Wizard', 'Merlin', 'Magic'] (male)
- PPzYpIqttlTYA83688JI: ['Pirate', 'Adventerous'] (male)
- ZF6FPAbjXT4488VcRRnw: ['Young', 'British', 'Bookworm'] (female)
- y2Y5MeVPm6ZQXK64WUui: ['Old', 'Storyteller', 'Wise'] (male)
- Wu86LpENEn32PwtU2hv1: ['Deeper', 'Cheery'] (female)
- FUfBrNit0NNZAwb58KWH: ['Generic', 'Main Character'] (female)
- EkK5I93UQWFDigLMpZcX: ['Deep', 'Main Character','Narrator'] (male)
- qBDvhofpxp92JgXJxDjB: ['Female', 'calming', 'youthful'] (female)
- c7XGL37TTXR5zdorzHX9: ['Gossipy', 'Sassy', 'Teenager'] (female)
- 3vk47KpWZzIrWkdEhumS: ['Chatty', 'Laid back'] (male)
- b3tuFWghbXYRa9Cs9MJf: ['Narrator', 'Deep'] (male)
- 0TfZ4rvne3QI7UjDxVkM: ['Childlike', 'High pitched'] (female)

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
                    "7tRwuZTD1EWi6nydVerp",
                    "cfc7wVYq4gw4OpcEEAom",
                    "vfaqCOvlrKi4Zp7C2IAm",
                    "yjJ45q8TVCrtMhEKurxY",
                    "oR4uRy4fHDUGGISL0Rev",
                    "PPzYpIqttlTYA83688JI",
                    "ZF6FPAbjXT4488VcRRnw",
                    "y2Y5MeVPm6ZQXK64WUui",
                    "Wu86LpENEn32PwtU2hv1",
                    "FUfBrNit0NNZAwb58KWH",
                    "EkK5I93UQWFDigLMpZcX",
                    "qBDvhofpxp92JgXJxDjB",
                    "c7XGL37TTXR5zdorzHX9",
                    "3vk47KpWZzIrWkdEhumS",
                    "b3tuFWghbXYRa9Cs9MJf",
                    "0TfZ4rvne3QI7UjDxVkM",
                ],
            ),
            audio=AudioAssetsConfig(
                intro_filename="saintly_adventures_theme.mp3",
                outro_filename="saintly_adventures_theme.mp3",
            ),
            output=OutputConfig(filename_prefix="saintly_adventures"),
            linkage=PodcastLinkageConfig(podcast_slug="saintly-adventures"),
        )
    )


def create_full_podcast(target_date: date, publish_date: datetime.datetime = None) -> str:
    return _get_generator().create_full_podcast(target_date, publish_date)


def generate_next_day_podcast() -> str:
    return _get_generator().generate_next_day_podcast()


