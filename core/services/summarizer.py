import logging
from dataclasses import dataclass
from pathlib import Path

import anthropic
from jinja2 import Template

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "summarize_session.md"


@dataclass
class CharacterContext:
    """Minimal character info passed into prompt templates."""
    name: str
    player_name: str
    discord_user_id: int
    race: str | None = None
    character_class: str | None = None
    level: int | None = None


class SessionSummarizer:
    """Generates a narrative summary of a D&D session using Claude."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self._template = Template(PROMPT_PATH.read_text())

    async def summarize(
        self,
        transcript: str,
        characters: list[CharacterContext] | None = None,
        campaign_name: str | None = None,
        campaign_description: str | None = None,
        homebrew_context: str | None = None,
        srd_rules: str | None = None,
    ) -> str:
        """Generate a narrative summary from a session transcript.

        Returns the summary text.
        """
        prompt = self._template.render(
            transcript=transcript,
            characters=characters or [],
            campaign_name=campaign_name,
            campaign_description=campaign_description,
            homebrew_context=homebrew_context,
            srd_rules=srd_rules,
        )

        log.info(f"Requesting session summary ({len(transcript)} chars of transcript)")

        message = await self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        summary = message.content[0].text
        log.info(f"Summary generated ({len(summary)} chars)")
        return summary
