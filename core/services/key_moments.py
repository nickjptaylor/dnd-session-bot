import json
import logging
from dataclasses import dataclass
from pathlib import Path

import anthropic
from jinja2 import Template

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "extract_key_moments.md"


@dataclass
class ExtractedMoment:
    """A key moment extracted from the session transcript."""
    player_name: str
    discord_user_id: int | None
    description: str
    scene_prompt: str
    timestamp: str | None


class KeyMomentExtractor:
    """Extracts per-player key moments from a session transcript using Claude."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self._template = Template(PROMPT_PATH.read_text())

    async def extract(
        self,
        transcript: str,
        characters: list | None = None,
        homebrew_context: str | None = None,
        srd_rules: str | None = None,
    ) -> list[ExtractedMoment]:
        """Extract key moments from a session transcript.

        Returns a list of ExtractedMoment objects.
        """
        prompt = self._template.render(
            transcript=transcript,
            characters=characters or [],
            homebrew_context=homebrew_context,
            srd_rules=srd_rules,
        )

        log.info(f"Requesting key moment extraction ({len(transcript)} chars of transcript)")

        message = await self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text
        moments = self._parse_response(raw)
        log.info(f"Extracted {len(moments)} key moment(s)")
        return moments

    def _parse_response(self, raw: str) -> list[ExtractedMoment]:
        """Parse Claude's JSON response into ExtractedMoment objects."""
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            # Remove opening fence (```json or ```)
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            log.error(f"Failed to parse key moments JSON: {raw[:500]}")
            return []

        if not isinstance(data, list):
            log.error(f"Expected a JSON array, got {type(data).__name__}")
            return []

        moments = []
        for item in data:
            try:
                moments.append(ExtractedMoment(
                    player_name=item["player_name"],
                    discord_user_id=int(item["discord_user_id"]) if item.get("discord_user_id") else None,
                    description=item["description"],
                    scene_prompt=item["scene_prompt"],
                    timestamp=item.get("timestamp"),
                ))
            except KeyError as e:
                log.warning(f"Skipping malformed key moment (missing {e}): {item}")

        return moments
