import logging
from pathlib import Path

import anthropic
from jinja2 import Template

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "dm_coaching.md"


class DMCoach:
    """Generates DM coaching notes from a session transcript using Claude."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self._template = Template(PROMPT_PATH.read_text())

    async def coach(
        self,
        transcript: str,
        summary: str,
        campaign_name: str | None = None,
        homebrew_context: str | None = None,
        srd_rules: str | None = None,
    ) -> str:
        """Generate DM coaching notes based on the session.

        Returns coaching notes as a bulleted text string.
        """
        prompt = self._template.render(
            transcript=transcript,
            summary=summary,
            campaign_name=campaign_name,
            homebrew_context=homebrew_context,
            srd_rules=srd_rules,
        )

        log.info("Requesting DM coaching notes")

        message = await self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )

        notes = message.content[0].text
        log.info(f"DM coaching notes generated ({len(notes)} chars)")
        return notes
