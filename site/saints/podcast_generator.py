import os
import io
import json
import tempfile
import subprocess
import string
import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone
from django.utils.timezone import make_aware
from django.utils.text import slugify

from elevenlabs import DialogueInput, ElevenLabs
from pydantic import BaseModel, Field, model_validator

from saints.models import CalendarEvent, Podcast, PodcastEpisode
from saints.api import BiographySerializer

# Optional Google Search imports
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# ------------------------------
# Pydantic models (shared)
# ------------------------------


class StructuredBioModel(BaseModel):
    Title: str
    Calendars: List[str]
    Summary: str
    Themes: List[str]
    CommemorationIdeas: List[str]
    DiscussionQuestion: str
    Traditions: List[str] = []
    Legends: List[str] = []


class ResearchQueryModel(BaseModel):
    queries: List[str]


class StructuredResponse(BaseModel):
    feasts: List[StructuredBioModel]


# Adult show script models
class PodcastLineModel(BaseModel):
    PodcastHostName: str
    Content: str
    SystemInstructions: Optional[str] = None


class PodcastScriptModel(BaseModel):
    lines: List[PodcastLineModel]


# Kids show script models
class ScriptLineModel(BaseModel):
    character: str
    text: str


class VoiceAssignment(BaseModel):
    character: str
    voice_id: str


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
            raise ValueError(
                f"Missing voice assignments for characters: {', '.join(sorted(original_missing))}"
            )

        # Ensure script lines only use declared characters (case-insensitive comparison)
        line_characters = {l.character.strip().lower() for l in self.script_lines}
        unknown = line_characters - character_set
        if unknown:
            # Get the original character names that are unknown
            original_unknown = [
                l.character for l in self.script_lines if l.character.strip().lower() in unknown
            ]
            raise ValueError(
                f"script_lines reference undeclared characters: {', '.join(sorted(set(original_unknown)))}"
            )
        return self


# ------------------------------
# Config models
# ------------------------------


@dataclass
class AIConfig:
    provider: str = "openai"  # 'openai', 'grok', 'anthropic'
    model: str = "gpt-5"
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None


@dataclass
class VoiceConfig:
    mode: str = "fixed"  # 'fixed' or 'ai_assigned'
    fixed_voice_map: Dict[str, str] = field(default_factory=dict)
    allowed_voice_ids: List[str] = field(default_factory=list)


@dataclass
class AudioAssetsConfig:
    intro_filename: Optional[str] = None  # in MEDIA_ROOT/podcast_assets/
    outro_filename: Optional[str] = None


@dataclass
class OutputConfig:
    filename_prefix: str = "saints_and_seasons"


@dataclass
class PodcastLinkageConfig:
    podcast_uuid: Optional[str] = None
    podcast_slug: Optional[str] = None


@dataclass
class PromptsConfig:
    identify_research_queries_prompt: str
    structured_bio_prompt: str
    script_prompt_template: str  # Will be formatted with date string if needed


@dataclass
class GeneratorConfig:
    ai: AIConfig
    prompts: PromptsConfig
    voices: VoiceConfig
    audio: AudioAssetsConfig
    output: OutputConfig
    linkage: PodcastLinkageConfig


# ------------------------------
# Generator
# ------------------------------


class PodcastGenerator:
    def __init__(self, config: GeneratorConfig):
        self.config = config

    # --- AI helpers ---
    def _get_ai_client(self):
        cfg = self.config.ai
        if cfg.provider == "openai":
            from openai import OpenAI
            if cfg.base_url or cfg.api_key_env:
                api_key = os.getenv(cfg.api_key_env) if cfg.api_key_env else None
                return OpenAI(api_key=api_key, base_url=cfg.base_url)  # type: ignore
            return OpenAI()
        elif cfg.provider == "grok":
            from openai import OpenAI
            api_key = os.getenv(cfg.api_key_env or "XAI_API_KEY")
            if not api_key:
                raise ValueError("XAI_API_KEY environment variable is required for Grok")
            return OpenAI(api_key=api_key, base_url=cfg.base_url or "https://api.x.ai/v1")
        elif cfg.provider == "anthropic":
            from anthropic import Anthropic
            api_key = os.getenv(cfg.api_key_env or "ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable is required for Anthropic")
            return Anthropic(api_key=api_key)
        else:
            raise ValueError(f"Unsupported AI provider: {cfg.provider}")

    def _model_name(self) -> str:
        return self.config.ai.model

    def _structured_completion(self, messages: List[Dict[str, Any]], response_format_model: Any):
        provider = self.config.ai.provider
        print(f"[GEN] Using AI provider={provider}, model={self._model_name()}")
        model = self._model_name()
        client = self._get_ai_client()

        if provider == "openai":
            # Use OpenAI's structured output with .parse()
            response = client.beta.chat.completions.parse(
                model=model,
                messages=messages,
                response_format=response_format_model,
            )
            return response.choices[0].message.parsed
        elif provider == "anthropic":
            enhanced_messages = messages.copy()
            system_message = None
            if enhanced_messages and enhanced_messages[0]["role"] == "system":
                system_message = enhanced_messages[0]["content"]
                enhanced_messages = enhanced_messages[1:]
                # Create a simplified schema description
                if hasattr(response_format_model, "__name__") and response_format_model.__name__ == "PodcastScriptModel":
                    schema_description = '{"lines": [{"PodcastHostName": "string", "Content": "string", "SystemInstructions": "string"}]}'
                elif hasattr(response_format_model, "__name__") and response_format_model.__name__ == "KidsPodcastScriptModel":
                    schema_description = '{"title": "string", "saint_name": "string", "characters": ["string"], "script_lines": [{"character": "string", "text": "string"}], "voices": [{"character": "string", "voice_id": "string"}]}'
                elif hasattr(response_format_model, "__name__") and response_format_model.__name__ == "StructuredResponse":
                    schema_description = '{"feasts": [{"Title": "string", "Calendars": ["string"], "Summary": "string", "Themes": ["string"], "CommemorationIdeas": ["string"], "DiscussionQuestion": "string", "Traditions": ["string"]}]}'
                elif hasattr(response_format_model, "__name__") and response_format_model.__name__ == "ResearchQueryModel":
                    schema_description = '{"queries": ["string"]}'
                else:
                    schema_description = str(response_format_model.model_json_schema())
                system_message += (
                    f"\n\nIMPORTANT: Return your response as valid JSON that matches this exact structure: {schema_description}"
                )

            if system_message:
                response = client.messages.create(
                    model=model,
                    max_tokens=8000,
                    system=system_message,
                    messages=enhanced_messages,
                )
            else:
                response = client.messages.create(
                    model=model,
                    max_tokens=8000,
                    messages=enhanced_messages,
                )

            content = response.content[0].text
            if isinstance(content, str):
                import json as _json
                parsed_json = _json.loads(content)
                return response_format_model.model_validate(parsed_json)
            return content
        else:
            # Grok / OpenAI-compatible JSON mode
            enhanced_messages = messages.copy()
            if enhanced_messages and enhanced_messages[0]["role"] == "system":
                if hasattr(response_format_model, "__name__") and response_format_model.__name__ == "PodcastScriptModel":
                    schema_description = '{"lines": [{"PodcastHostName": "string", "Content": "string", "SystemInstructions": "string"}]}'
                elif hasattr(response_format_model, "__name__") and response_format_model.__name__ == "KidsPodcastScriptModel":
                    schema_description = '{"title": "string", "saint_name": "string", "characters": ["string"], "script_lines": [{"character": "string", "text": "string"}], "voices": [{"character": "string", "voice_id": "string"}]}'
                elif hasattr(response_format_model, "__name__") and response_format_model.__name__ == "StructuredResponse":
                    schema_description = '{"feasts": [{"Title": "string", "Calendars": ["string"], "Summary": "string", "Themes": ["string"], "CommemorationIdeas": ["string"], "DiscussionQuestion": "string", "Traditions": ["string"]}]}'
                elif hasattr(response_format_model, "__name__") and response_format_model.__name__ == "ResearchQueryModel":
                    schema_description = '{"queries": ["string"]}'
                else:
                    schema_description = str(response_format_model.model_json_schema())
                enhanced_messages[0]["content"] += (
                    f"\n\nIMPORTANT: Return your response as valid JSON that matches this exact structure: {schema_description}"
                )

            response = self._get_ai_client().chat.completions.create(
                model=model,
                messages=enhanced_messages,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            if isinstance(content, str):
                import json as _json
                parsed_json = _json.loads(content)
                return response_format_model.model_validate(parsed_json)
            return content

    # --- Data assembly helpers ---
    def _generate_podcast_filename(self, target_date: datetime.date) -> str:
        date_str = target_date.strftime("%Y_%m_%d")
        base_filename = f"{self.config.output.filename_prefix}_{date_str}.mp3"
        filename = base_filename
        suffix_iter = iter(string.ascii_lowercase)
        podcasts_dir = "podcasts/"
        while default_storage.exists(os.path.join(podcasts_dir, filename)):
            suffix = next(suffix_iter)
            filename = f"{self.config.output.filename_prefix}_{date_str}_{suffix}.mp3"
        return filename

    def _get_biographies_for_day(self, target_date: datetime.date) -> List[Dict[str, Any]]:
        print(f"[GEN] Fetching biographies for {target_date}")
        calendar_priority = [
            "catholic",
            "Divino Afflatu - 1954",
            "Rubrics 1960 - 1960",
            "ordinariate",
        ]
        events = CalendarEvent.objects.filter(date=target_date, calendar__in=calendar_priority)
        if not events.exists():
            return []
        events_by_calendar: Dict[str, List[Any]] = {}
        for event in events:
            if hasattr(event, "biography") and event.biography:
                cal = event.calendar
                if cal not in events_by_calendar:
                    events_by_calendar[cal] = []
                events_by_calendar[cal].append(event.biography)

        prioritized_biographies: List[Any] = []
        for cal in calendar_priority:
            if cal in events_by_calendar:
                prioritized_biographies.extend(events_by_calendar[cal])

        return BiographySerializer(prioritized_biographies, many=True).data

    def _identify_research_queries(self, bios: List[Dict[str, Any]]) -> List[str]:
        print("[GEN] Identifying research queries from bios")
        prompt = self.config.prompts.identify_research_queries_prompt
        result = self._structured_completion(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt + "\n" + json.dumps(bios)},
            ],
            response_format_model=ResearchQueryModel,
        )
        return result.queries

    def _perform_google_search(self, query: str, api_key: str, cse_id: str) -> List[Dict[str, Any]]:
        try:
            service = build("customsearch", "v1", developerKey=api_key)
            search_query = f"{query} Catholic saint feast tradition"
            result = (
                service.cse()
                .list(q=search_query, cx=cse_id, num=5, safe="active", lr="lang_en")
                .execute()
            )
            items = result.get("items", [])
            return [
                {
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "link": item.get("link", ""),
                    "displayLink": item.get("displayLink", ""),
                }
                for item in items
            ]
        except HttpError:
            return []
        except Exception:
            return []

    def _synthesize_search_results(self, query: str, search_results: List[Dict[str, Any]]) -> str:
        if not search_results:
            return self._fallback_ai_research([query])[0]["summary"]

        search_data = {"query": query, "results": search_results}
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

        provider = self.config.ai.provider
        model = self._model_name()
        client = self._get_ai_client()

        try:
            if provider == "anthropic":
                response = client.messages.create(
                    model=model,
                    max_tokens=1000,
                    messages=[
                        {"role": "user", "content": f"You are a knowledgeable Catholic researcher and podcast content creator.\n\n{prompt}"}
                    ],
                )
                return response.content[0].text.strip()
            else:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a knowledgeable Catholic researcher and podcast content creator.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                )
                return response.choices[0].message.content.strip()
        except Exception:
            snippets = [r.get("snippet", "") for r in search_results[:3]]
            return f"Research on {query}: {' '.join(snippets)}"

    def _fallback_ai_research(self, queries: List[str]) -> List[Dict[str, str]]:
        print("[GEN] Supplementing with web searches where available")
        results: List[Dict[str, str]] = []
        provider = self.config.ai.provider
        model = self._model_name()
        client = self._get_ai_client()
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
                if provider == "anthropic":
                    response = client.messages.create(
                        model=model,
                        max_tokens=1000,
                        messages=[
                            {"role": "user", "content": f"You are a knowledgeable Catholic researcher and podcast content creator.\n\n{prompt}"}
                        ],
                    )
                    summary = response.content[0].text.strip()
                else:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a knowledgeable Catholic researcher and podcast content creator.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                    )
                    summary = response.choices[0].message.content.strip()
                results.append({"query": query, "summary": summary, "sources": []})
            except Exception:
                results.append({"query": query, "summary": f"Research summary for: {query}", "sources": []})
        return results

    def _supplement_with_searches(self, queries: List[str]) -> List[Dict[str, str]]:
        google_api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
        google_cse_id = os.getenv("GOOGLE_CUSTOM_SEARCH_ENGINE_ID")
        if not google_api_key or not google_cse_id:
            return self._fallback_ai_research(queries)
        results: List[Dict[str, str]] = []
        for q in queries:
            try:
                search_results = self._perform_google_search(q, google_api_key, google_cse_id)
                summary = self._synthesize_search_results(q, search_results)
                results.append(
                    {
                        "query": q,
                        "summary": summary,
                        "sources": [r.get("link", "") for r in search_results[:3]],
                    }
                )
            except Exception:
                ai_summary = self._fallback_ai_research([q])[0]["summary"]
                results.append({"query": q, "summary": ai_summary, "sources": []})
        return results

    def _get_structured_bio_summary(
        self, bios: List[Dict[str, Any]], search_results: List[Dict[str, str]]
    ) -> List[StructuredBioModel]:
        print("[GEN] Creating structured summaries of biographies")
        prompt = self.config.prompts.structured_bio_prompt
        merged_data = {"biographies": bios, "search_summaries": search_results}
        result = self._structured_completion(
            messages=[
                {"role": "system", "content": "You are a podcast script writer."},
                {"role": "user", "content": prompt + "\n" + json.dumps(merged_data)},
            ],
            response_format_model=StructuredResponse,
        )
        return result.feasts

    def _generate_podcast_script(
        self,
        structured_bios: List[StructuredBioModel],
        target_date: datetime.date,
        original_bios: Optional[List[Dict[str, Any]]] = None,
    ):
        date_str = target_date.strftime("%B %d, %Y")
        print(f"[GEN] Generating script for {date_str}")
        # Only substitute the {date} token; avoid str.format which would treat other
        # literal braces in the prompt template (e.g., JSON examples) as placeholders.
        template = self.config.prompts.script_prompt_template
        prompt = template.replace("{date}", date_str)
        data_payload: Dict[str, Any] = {
            "structured_summaries": [s.model_dump() for s in structured_bios]
        }
        if original_bios:
            data_payload["original_biography_data"] = original_bios

        # Decide script model based on voice mode
        use_kids = self.config.voices.mode == "ai_assigned"
        response_model = KidsPodcastScriptModel if use_kids else PodcastScriptModel

        result = self._structured_completion(
            messages=[
                {
                    "role": "system",
                    "content": "You are a creative and passionate podcast scriptwriter who specializes in making Catholic content exciting and engaging.",
                },
                {"role": "user", "content": prompt + "\n\nDATA:\n" + json.dumps(data_payload)},
            ],
            response_format_model=response_model,
        )
        print("[GEN] Script generation complete")
        return result

    # --- TTS helpers ---

    def _normalize_script_and_voice_map(
        self, script_obj: Any
    ) -> Tuple[List[Dict[str, str]], Dict[str, str]]:
        normalized_lines: List[Dict[str, str]] = []
        voice_map: Dict[str, str] = {}
        if isinstance(script_obj, KidsPodcastScriptModel):
            for l in script_obj.script_lines:
                normalized_lines.append({"speaker": l.character, "text": l.text})
            # Build voice map from AI output and validate allowed list if provided
            voice_map = {v.character: v.voice_id for v in script_obj.voices}
            if self.config.voices.allowed_voice_ids:
                invalid = [vid for vid in voice_map.values() if vid not in self.config.voices.allowed_voice_ids]
                if invalid:
                    raise ValueError(
                        f"AI selected unsupported voice ids: {', '.join(sorted(set(invalid)))}"
                    )
        else:
            # Adult dialogue model
            for l in script_obj.lines:  # type: ignore[attr-defined]
                normalized_lines.append({"speaker": l.PodcastHostName, "text": l.Content})
            voice_map = dict(self.config.voices.fixed_voice_map)
        return normalized_lines, voice_map

    def _generate_tts_and_merge(
        self, normalized_lines: List[Dict[str, str]], voice_map: Dict[str, str], target_date: datetime.date
    ) -> str:
        if not isinstance(target_date, datetime.date):
            raise TypeError(f"target_date must be a datetime.date, not {type(target_date)}")

        api_key = os.getenv("ELEVEN_LABS_API_KEY")
        if not api_key:
            raise ValueError("ELEVEN_LABS_API_KEY environment variable is required")
        client = ElevenLabs(api_key=api_key)

        temp_dir = tempfile.mkdtemp()

        print(f"[GEN] Generating dialogue with ElevenLabs v3 for {len(normalized_lines)} lines")

        # Build DialogueInput list, splitting overly long lines into smaller chunks
        def _chunk_text(text: str, max_chunk_len: int = 900) -> List[str]:
            """Chunk text while respecting ElevenLabs v3 bracketed tags.
            - Never split inside square-bracket tags like [warmly] or [church bells].
            - Prefer to split on whitespace when not inside a tag.
            - If a tag would cross the boundary, extend the chunk until the tag closes.
            """
            if len(text) <= max_chunk_len:
                return [text]
            chunks: List[str] = []
            i = 0
            n = len(text)
            min_soft_len = int(max_chunk_len * 0.6)
            while i < n:
                start = i
                bracket_depth = 0
                last_ws_outside = -1
                j = i
                # First pass: advance up to max_chunk_len, track bracket depth and last whitespace outside tags
                while j < n and (j - start) < max_chunk_len:
                    ch = text[j]
                    if ch == "[":
                        bracket_depth += 1
                    elif ch == "]":
                        if bracket_depth > 0:
                            bracket_depth -= 1
                    if ch.isspace() and bracket_depth == 0:
                        last_ws_outside = j
                    j += 1

                cut: int
                if j >= n:
                    cut = n
                else:
                    if bracket_depth > 0:
                        # We are inside a tag at the boundary; keep going until tag closes
                        while j < n and bracket_depth > 0:
                            ch = text[j]
                            if ch == "[":
                                bracket_depth += 1
                            elif ch == "]":
                                bracket_depth -= 1
                            j += 1
                        # Optionally, extend to next whitespace for natural pause
                        while j < n and not text[j].isspace():
                            j += 1
                        cut = j
                    else:
                        # Prefer to cut at the last whitespace outside tags if far enough into the window
                        if last_ws_outside != -1 and (last_ws_outside - start) >= min_soft_len:
                            cut = last_ws_outside
                        else:
                            cut = j

                piece = text[start:cut].strip()
                if piece:
                    chunks.append(piece)
                i = cut
                # Skip any subsequent whitespace so the next piece starts on content
                while i < n and text[i].isspace():
                    i += 1
            return chunks

        flat_inputs: List[DialogueInput] = []
        for line in normalized_lines:
            speaker = line["speaker"]
            if speaker not in voice_map:
                raise KeyError(f"No voice_id provided for speaker: {speaker}")
            voice_id = voice_map[speaker]
            # Preserve ElevenLabs v3 bracketed tags and chunk safely around them
            text_for_dialogue = line["text"]
            for piece in _chunk_text(text_for_dialogue):
                piece = piece.strip()
                if not piece:
                    continue
                flat_inputs.append(DialogueInput(text=piece, voice_id=voice_id))

        # Batch inputs to respect ElevenLabs v3 request limit (max 3000 chars total text)
        MAX_REQ_CHARS = 2500
        batches: List[List[DialogueInput]] = []
        current_batch: List[DialogueInput] = []
        current_len = 0
        for di in flat_inputs:
            piece_len = len(di.text)  # type: ignore[attr-defined]
            if current_batch and current_len + piece_len > MAX_REQ_CHARS:
                batches.append(current_batch)
                current_batch = [di]
                current_len = piece_len
            else:
                current_batch.append(di)
                current_len += piece_len
        if current_batch:
            batches.append(current_batch)

        if not batches:
            raise RuntimeError("No dialogue inputs were prepared for TTD")

        part_files: List[str] = []
        for bidx, batch in enumerate(batches):
            try:
                response = client.text_to_dialogue.convert(
                    inputs=batch,
                    model_id="eleven_v3",
                    output_format="mp3_44100_128",
                )
            except Exception as e:
                raise RuntimeError(f"Failed to generate dialogue audio for batch {bidx}: {e}")

            part_path = os.path.join(temp_dir, f"dialogue_part_{bidx}.mp3")
            with open(part_path, "wb") as f:
                if isinstance(response, (bytes, bytearray)):
                    f.write(response)
                else:
                    for chunk in response:
                        if chunk:
                            f.write(chunk)
            part_files.append(part_path)

        # Concatenate all parts into a single raw dialogue file
        raw_dialogue_path = os.path.join(temp_dir, "dialogue_raw.mp3")
        if len(part_files) == 1:
            raw_dialogue_path = part_files[0]
        else:
            print(f"[GEN] Concatenating {len(part_files)} dialogue parts")
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                ]
                + sum([["-i", f] for f in part_files], [])
                + [
                    "-filter_complex",
                    f"concat=n={len(part_files)}:v=0:a=1[dialogue]",
                    "-map",
                    "[dialogue]",
                    "-c:a",
                    "libmp3lame",
                    "-b:a",
                    "128k",
                    raw_dialogue_path,
                ],
                capture_output=True,
                check=True,
            )

        filename = self._generate_podcast_filename(target_date)
        podcasts_dir = "podcasts/"
        merged_path = os.path.join(temp_dir, filename)

        # Normalize dialogue audio before mixing with music
        dialogue_path = os.path.join(temp_dir, "dialogue.mp3")
        print("[GEN] Normalizing dialogue audio")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                raw_dialogue_path,
                "-filter_complex",
                "[0:a]loudnorm=I=-16:LRA=11:TP=-1.5[final]",
                "-map",
                "[final]",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "128k",
                dialogue_path,
            ],
            capture_output=True,
            check=True,
        )

        # Prepare music assets
        def _safe_path(name: Optional[str]) -> Optional[str]:
            if not name:
                return None
            p = os.path.join(settings.MEDIA_ROOT, "podcast_assets", name)
            return p if os.path.exists(p) else None

        intro_music_path = _safe_path(self.config.audio.intro_filename)
        outro_music_path = _safe_path(self.config.audio.outro_filename)

        # We already have a single dialogue file; proceed to music merge

        def get_audio_duration(file_path: str) -> float:
            try:
                result = subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "quiet",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "csv=p=0",
                        file_path,
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return float(result.stdout.strip())
            except Exception:
                return 10.0

        if intro_music_path and outro_music_path:
            print("[GEN] Merging intro + dialogue + outro with normalization")
            intro_duration = get_audio_duration(intro_music_path)
            outro_duration = get_audio_duration(outro_music_path)
            intro_fade_start = max(0.0, intro_duration - 2.0)
            outro_fade_start = max(0.0, outro_duration - 2.0)
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    intro_music_path,
                    "-i",
                    dialogue_path,
                    "-i",
                    outro_music_path,
                    "-filter_complex",
                    f"[0:a]afade=t=out:st={intro_fade_start}:d=2[intro_faded];"
                    f"[2:a]afade=t=out:st={outro_fade_start}:d=2[outro_faded];"
                    f"[intro_faded][1:a][outro_faded]concat=n=3:v=0:a=1[mixed];"
                    f"[mixed]loudnorm=I=-16:LRA=11:TP=-1.5[final]",
                    "-map",
                    "[final]",
                    "-c:a",
                    "libmp3lame",
                    "-b:a",
                    "128k",
                    merged_path,
                ],
                capture_output=True,
                check=True,
            )
        elif intro_music_path:
            print("[GEN] Merging intro + dialogue with normalization")
            intro_duration = get_audio_duration(intro_music_path)
            intro_fade_start = max(0.0, intro_duration - 2.0)
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    intro_music_path,
                    "-i",
                    dialogue_path,
                    "-filter_complex",
                    f"[0:a]afade=t=out:st={intro_fade_start}:d=2[intro_faded];"
                    f"[intro_faded][1:a]concat=n=2:v=0:a=1[mixed];"
                    f"[mixed]loudnorm=I=-16:LRA=11:TP=-1.5[final]",
                    "-map",
                    "[final]",
                    "-c:a",
                    "libmp3lame",
                    "-b:a",
                    "128k",
                    merged_path,
                ],
                capture_output=True,
                check=True,
            )
        elif outro_music_path:
            print("[GEN] Merging dialogue + outro with normalization")
            outro_duration = get_audio_duration(outro_music_path)
            outro_fade_start = max(0.0, outro_duration - 2.0)
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    dialogue_path,
                    "-i",
                    outro_music_path,
                    "-filter_complex",
                    f"[1:a]afade=t=out:st={outro_fade_start}:d=2[outro_faded];"
                    f"[0:a][outro_faded]concat=n=2:v=0:a=1[mixed];"
                    f"[mixed]loudnorm=I=-16:LRA=11:TP=-1.5[final]",
                    "-map",
                    "[final]",
                    "-c:a",
                    "libmp3lame",
                    "-b:a",
                    "128k",
                    merged_path,
                ],
                capture_output=True,
                check=True,
            )
        else:
            print("[GEN] No music assets found; normalizing dialogue only")
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    dialogue_path,
                    "-filter_complex",
                    "[0:a]loudnorm=I=-16:LRA=11:TP=-1.5[final]",
                    "-map",
                    "[final]",
                    "-c:a",
                    "libmp3lame",
                    "-b:a",
                    "128k",
                    merged_path,
                ],
                capture_output=True,
                check=True,
            )

        with open(merged_path, "rb") as f:
            default_storage.save(os.path.join(podcasts_dir, filename), ContentFile(f.read()))
        print(f"[GEN] Saved episode audio to podcasts/{filename}")
        return os.path.join(podcasts_dir, filename)

    # --- Metadata and persistence ---
    def _generate_episode_metadata(
        self,
        structured: List[StructuredBioModel],
        normalized_lines: List[Dict[str, str]],
        target_date: datetime.date,
        audio_path: str,
    ) -> Dict[str, Any]:
        provider = self.config.ai.provider
        print("[GEN] Generating episode metadata")
        model = self._model_name()
        client = self._get_ai_client()
        import json as _json

        episode_names = [s.Title for s in structured]
        date_str = target_date.strftime("%Y-%m-%d")
        pretty_date = target_date.strftime("%B %d, %Y")
        day_url = f"https://saints.benlocher.com/day/{date_str}/?calendar=current"
        context = {
            "date": pretty_date,
            "saints_and_feasts": episode_names,
            "script": normalized_lines,
            "day_url": day_url,
        }

        # Title
        try:
            title_prompt = (
                "Given this list of saint and feast names, return a single string suitable for use as a podcast episode title. "
                "Remove duplicates, and format the list with commas and 'and' before the last item. Do not add anything else. "
                "List: "
                + _json.dumps(episode_names)
            )
            if provider == "anthropic":
                title_response = client.messages.create(
                    model=model,
                    max_tokens=100,
                    messages=[{"role": "user", "content": f"You are a helpful assistant.\n\n{title_prompt}"}],
                )
                ai_title = title_response.content[0].text.strip()
            else:
                title_response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": title_prompt},
                    ],
                    response_format={"type": "text"},
                )
                ai_title = title_response.choices[0].message.content.strip()
            if ai_title.startswith('"') and ai_title.endswith('"'):
                ai_title = ai_title[1:-1]
            episode_name = f"{pretty_date}: {ai_title}"
        except Exception:
            episode_name = f"{pretty_date}: {', '.join(episode_names)}"

        # Subtitle + descriptions
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
            if provider == "anthropic":
                response = client.messages.create(
                    model=model,
                    max_tokens=1000,
                    messages=[{"role": "user", "content": f"You are a creative Catholic podcast producer.\n\n{prompt}"}],
                )
                ai_result = response.content[0].text
            else:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a creative Catholic podcast producer."},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                )
                ai_result = response.choices[0].message.content
            if isinstance(ai_result, str):
                ai_result = _json.loads(ai_result)
            subtitle = ai_result.get("subtitle")
            short_desc = ai_result.get("short_description")
            long_desc = ai_result.get("long_description")
        except Exception:
            subtitle = structured[0].Summary if structured and hasattr(structured[0], "Summary") else episode_name
            short_desc = f"For more, see {day_url}. "
            if structured and hasattr(structured[0], "Summary"):
                short_desc += structured[0].Summary.split(". ")[0] + "."
            else:
                short_desc += episode_name
            long_desc = f"For more, see {day_url}.\n\n"
            for s in structured:
                long_desc += f"<b>{s.Title}</b>\n{s.Summary}\n\n"

        full_text = "\n".join([f"{l['speaker']}: {l['text']}" for l in normalized_lines])
        slug_base = f"{date_str}-{episode_names[0] if episode_names else 'episode'}"
        slug = slugify(slug_base)[:50]
        orig_slug = slug
        i = 1
        while PodcastEpisode.objects.filter(slug=slug).exists():
            slug = f"{orig_slug}-{i}"
            i += 1
        file_name = audio_path.split("/")[-1]
        print(f"[GEN] Metadata ready (slug={slug}, title={episode_name})")
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

    @staticmethod
    def _create_publish_date(publish_date: Optional[datetime.datetime] = None):
        from zoneinfo import ZoneInfo
        if publish_date:
            if timezone.is_naive(publish_date):
                publish_date = make_aware(publish_date)
            base = publish_date
        else:
            base = timezone.now()
        eastern_tz = ZoneInfo("America/New_York")
        eastern_time = base.astimezone(eastern_tz)
        eastern_5pm = eastern_time.replace(hour=17, minute=0, second=0, microsecond=0)
        return eastern_5pm.astimezone(ZoneInfo("UTC"))

    def _create_podcast_episode(
        self, metadata: Dict[str, Any], publish_date: Optional[datetime.datetime] = None
    ) -> None:
        from mutagen.mp3 import MP3
        import os as _os

        podcast: Optional[Podcast] = None
        if self.config.linkage.podcast_uuid:
            try:
                podcast = Podcast.objects.get(pk=self.config.linkage.podcast_uuid)
            except Podcast.DoesNotExist:
                podcast = None
        if not podcast and self.config.linkage.podcast_slug:
            try:
                podcast = Podcast.objects.get(slug=self.config.linkage.podcast_slug)
            except Podcast.DoesNotExist:
                podcast = None
        if not podcast:
            # Final fallback to previous behavior
            podcast = Podcast.objects.filter(religion="catholic").order_by("-created").first()

        last_episode = (
            PodcastEpisode.objects.filter(podcast=podcast).order_by("-episode_number").first()
            if podcast
            else None
        )
        episode_number = (
            (last_episode.episode_number or 0) + 1 if last_episode and last_episode.episode_number else 1
        )

        audio_path = metadata.get("file_name")
        duration: Optional[int] = None
        if audio_path:
            media_path = os.path.join(settings.MEDIA_ROOT, "podcasts", audio_path)
            if os.path.exists(media_path):
                try:
                    audio = MP3(media_path)
                    duration = int(audio.info.length)
                except Exception:
                    duration = None

        final_publish_date = self._create_publish_date(publish_date)
        print(f"[GEN] Creating PodcastEpisode (episode_number={episode_number})")

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

    # --- Public orchestration methods ---
    def create_full_podcast(
        self, target_date: datetime.date, publish_date: Optional[datetime.datetime] = None
    ) -> str:
        print("[GEN] Starting full podcast generation")
        if not isinstance(target_date, datetime.date):
            raise TypeError(f"target_date must be a datetime.date, not {type(target_date)}")
        bios = self._get_biographies_for_day(target_date)
        print(f"[GEN] Bios fetched: {len(bios)}")
        research_queries = self._identify_research_queries(bios)
        print(f"[GEN] Research queries: {len(research_queries)}")
        search_results = self._supplement_with_searches(research_queries)
        print(f"[GEN] Search summaries: {len(search_results)}")
        structured = self._get_structured_bio_summary(bios, search_results)
        print(f"[GEN] Structured feasts: {len(structured)}")
        script_obj = self._generate_podcast_script(structured, target_date, bios)
        normalized_lines, voice_map = self._normalize_script_and_voice_map(script_obj)
        print(f"[GEN] Lines: {len(normalized_lines)}; Voices: {len(voice_map)}")
        audio_rel_path = self._generate_tts_and_merge(normalized_lines, voice_map, target_date)
        metadata = self._generate_episode_metadata(structured, normalized_lines, target_date, audio_rel_path)
        self._create_podcast_episode(metadata, publish_date)
        print("[GEN] Podcast generation complete")
        return audio_rel_path

    def generate_next_day_podcast(self) -> Optional[str]:
        from zoneinfo import ZoneInfo
        eastern_tz = ZoneInfo("America/New_York")
        eastern_now = timezone.now().astimezone(eastern_tz)
        tomorrow = eastern_now.date() + datetime.timedelta(days=1)
        # Determine which podcast this generator is targeting
        podcast: Optional[Podcast] = None
        if self.config.linkage.podcast_uuid:
            try:
                podcast = Podcast.objects.get(pk=self.config.linkage.podcast_uuid)
            except Podcast.DoesNotExist:
                podcast = None
        if not podcast and self.config.linkage.podcast_slug:
            try:
                podcast = Podcast.objects.get(slug=self.config.linkage.podcast_slug)
            except Podcast.DoesNotExist:
                podcast = None
        if not podcast:
            podcast = Podcast.objects.filter(religion="catholic").order_by("-created").first()

        # Only block if an episode for this specific podcast already exists for tomorrow
        if PodcastEpisode.objects.filter(date=tomorrow, podcast=podcast).exists():
            return None
        today_5pm = self._create_publish_date(None)
        return self.create_full_podcast(tomorrow, today_5pm)


# ------------------------------
# Ready-made prompt presets
# ------------------------------


        print("[GEN] Removed inline preset constants; using presets from wrapper modules")


