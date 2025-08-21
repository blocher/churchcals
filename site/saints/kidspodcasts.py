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
    "Use valid JSON only."
)

KIDS_SCRIPT_PROMPT_TEMPLATE = (
    "You are creating an exciting and engaging Catholic podcast script for kids called 'Saintly Adventures' for {date}.\n"
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


def _get_generator() -> PodcastGenerator:
    return PodcastGenerator(
        GeneratorConfig(
            ai=AIConfig(provider="openai", model="gpt-4.1"),
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


