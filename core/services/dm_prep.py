"""DM prep services — thread extraction, session intros, and plot hook generation.

Uses Claude to analyze session history and generate prep material for the DM.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import anthropic
from jinja2 import Template

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _strip_json_fences(raw: str) -> str:
    """Strip markdown code fences from Claude's JSON response."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


# --- Thread Extraction ---


@dataclass
class ExtractedThread:
    """A story thread extracted from a session summary."""

    title: str
    description: str
    thread_type: str
    is_new: bool
    existing_thread_id: str | None = None
    resolved: bool = False


class ThreadExtractor:
    """Extracts unresolved story threads from session summaries using Claude."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self._template = Template((PROMPTS_DIR / "extract_threads.md").read_text())

    async def extract(
        self,
        summary: str,
        existing_threads: list[dict] | None = None,
        campaign_name: str | None = None,
        homebrew_context: str | None = None,
    ) -> list[ExtractedThread]:
        """Extract story threads from a session summary.

        Args:
            summary: The narrative summary text
            existing_threads: Currently active threads [{id, title, description}]
            campaign_name: Name of the campaign
            homebrew_context: Homebrew lore/rules for context

        Returns:
            List of ExtractedThread objects (new and updated/resolved)
        """
        prompt = self._template.render(
            summary=summary,
            existing_threads=existing_threads or [],
            campaign_name=campaign_name,
            homebrew_context=homebrew_context,
        )

        log.info(f"Requesting thread extraction ({len(summary)} chars of summary)")

        message = await self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text
        return self._parse_response(raw)

    def _parse_response(self, raw: str) -> list[ExtractedThread]:
        """Parse Claude's JSON response into ExtractedThread objects."""
        text = _strip_json_fences(raw)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            log.error(f"Failed to parse threads JSON: {raw[:500]}")
            return []

        if not isinstance(data, list):
            log.error(f"Expected a JSON array, got {type(data).__name__}")
            return []

        threads = []
        for item in data:
            try:
                threads.append(ExtractedThread(
                    title=item["title"],
                    description=item["description"],
                    thread_type=item.get("thread_type", "other"),
                    is_new=item.get("is_new", True),
                    existing_thread_id=item.get("existing_thread_id"),
                    resolved=item.get("resolved", False),
                ))
            except KeyError as e:
                log.warning(f"Skipping malformed thread (missing {e}): {item}")

        log.info(f"Extracted {len(threads)} thread(s)")
        return threads


# --- Session Intro Generation ---


@dataclass
class CharacterInfo:
    """Character info for prompt context."""

    name: str
    race: str | None = None
    character_class: str | None = None
    level: int | None = None
    description: str | None = None


class IntroGenerator:
    """Generates dramatic session intro read-aloud text using Claude."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self._template = Template((PROMPTS_DIR / "session_intro.md").read_text())

    async def generate(
        self,
        recent_summaries: list[str],
        active_threads: list[dict] | None = None,
        characters: list[CharacterInfo] | None = None,
        campaign_name: str | None = None,
        campaign_description: str | None = None,
    ) -> str:
        """Generate a 'last time on...' read-aloud intro.

        Args:
            recent_summaries: Last 1-3 session summaries (oldest first)
            active_threads: Active story threads [{id, title, description, thread_type}]
            characters: Party members
            campaign_name: Name of the campaign
            campaign_description: Campaign description

        Returns:
            The generated intro text
        """
        # Truncate long summaries to avoid token limits
        trimmed = [s[:3000] for s in recent_summaries]

        prompt = self._template.render(
            recent_sessions=trimmed,
            active_threads=active_threads or [],
            characters=characters or [],
            campaign_name=campaign_name,
            campaign_description=campaign_description,
        )

        log.info(f"Requesting session intro ({len(recent_summaries)} summaries)")

        message = await self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        intro = message.content[0].text
        log.info(f"Session intro generated ({len(intro)} chars)")
        return intro


# --- Plot Hook Suggestions ---


@dataclass
class SuggestedHook:
    """A Claude-suggested plot hook."""

    title: str
    description: str
    hook_type: str | None
    related_thread_id: str | None = None


class HookSuggester:
    """Suggests plot hooks based on campaign context using Claude."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self._template = Template((PROMPTS_DIR / "suggest_plot_hooks.md").read_text())

    async def suggest(
        self,
        active_threads: list[dict],
        characters: list[CharacterInfo] | None = None,
        campaign_name: str | None = None,
        campaign_description: str | None = None,
        homebrew_context: str | None = None,
        recent_summary: str | None = None,
    ) -> list[SuggestedHook]:
        """Suggest plot hooks for the next session.

        Args:
            active_threads: Active story threads [{id, title, description, thread_type}]
            characters: Party members
            campaign_name: Name of the campaign
            campaign_description: Campaign description
            homebrew_context: Homebrew lore/rules
            recent_summary: Most recent session summary for context

        Returns:
            List of SuggestedHook objects
        """
        prompt = self._template.render(
            active_threads=active_threads or [],
            characters=characters or [],
            campaign_name=campaign_name,
            campaign_description=campaign_description,
            homebrew_context=homebrew_context,
            recent_summary=recent_summary[:3000] if recent_summary else None,
        )

        log.info("Requesting plot hook suggestions")

        message = await self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text
        return self._parse_response(raw)

    def _parse_response(self, raw: str) -> list[SuggestedHook]:
        """Parse Claude's JSON response into SuggestedHook objects."""
        text = _strip_json_fences(raw)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            log.error(f"Failed to parse hooks JSON: {raw[:500]}")
            return []

        if not isinstance(data, list):
            log.error(f"Expected a JSON array, got {type(data).__name__}")
            return []

        hooks = []
        for item in data:
            try:
                hooks.append(SuggestedHook(
                    title=item["title"],
                    description=item["description"],
                    hook_type=item.get("hook_type"),
                    related_thread_id=item.get("related_thread_id"),
                ))
            except KeyError as e:
                log.warning(f"Skipping malformed hook (missing {e}): {item}")

        log.info(f"Generated {len(hooks)} plot hook(s)")
        return hooks
