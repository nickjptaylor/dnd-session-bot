"""Builds campaign world context from homebrew content for LLM prompts."""

import logging
from dataclasses import dataclass, field

from sqlalchemy import select

from core.db import async_session
from core.models.campaign import Campaign, HomebrewContent

log = logging.getLogger(__name__)


@dataclass
class CampaignWorldContext:
    """All homebrew content for a campaign, organized by type."""

    campaign_name: str | None = None
    campaign_description: str | None = None
    npcs: list[dict] = field(default_factory=list)
    locations: list[dict] = field(default_factory=list)
    lore: list[dict] = field(default_factory=list)
    rules: list[dict] = field(default_factory=list)
    items: list[dict] = field(default_factory=list)

    @property
    def has_homebrew(self) -> bool:
        return bool(self.npcs or self.locations or self.lore or self.rules or self.items)

    def format_for_prompt(self) -> str:
        """Format all homebrew content into a text block for LLM prompts."""
        if not self.has_homebrew:
            return ""

        sections = []

        if self.npcs:
            lines = ["### NPCs"]
            for npc in self.npcs:
                lines.append(f"- **{npc['title']}**: {npc['content']}")
            sections.append("\n".join(lines))

        if self.locations:
            lines = ["### Locations"]
            for loc in self.locations:
                lines.append(f"- **{loc['title']}**: {loc['content']}")
            sections.append("\n".join(lines))

        if self.lore:
            lines = ["### World Lore"]
            for entry in self.lore:
                lines.append(f"- **{entry['title']}**: {entry['content']}")
            sections.append("\n".join(lines))

        if self.rules:
            lines = ["### Homebrew Rules"]
            for rule in self.rules:
                lines.append(f"- **{rule['title']}**: {rule['content']}")
            sections.append("\n".join(lines))

        if self.items:
            lines = ["### Notable Items"]
            for item in self.items:
                lines.append(f"- **{item['title']}**: {item['content']}")
            sections.append("\n".join(lines))

        return "\n\n".join(sections)


async def build_campaign_context(campaign_id) -> CampaignWorldContext:
    """Fetch campaign info and all homebrew content, organized by type."""
    ctx = CampaignWorldContext()

    async with async_session() as db:
        # Get campaign basics
        result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if not campaign:
            return ctx

        ctx.campaign_name = campaign.name
        ctx.campaign_description = campaign.description

        # Get all homebrew content
        result = await db.execute(
            select(HomebrewContent)
            .where(HomebrewContent.campaign_id == campaign_id)
            .order_by(HomebrewContent.content_type, HomebrewContent.title)
        )
        entries = result.scalars().all()

    type_map = {
        "npc": ctx.npcs,
        "location": ctx.locations,
        "lore": ctx.lore,
        "rule": ctx.rules,
        "item": ctx.items,
    }

    for entry in entries:
        target = type_map.get(entry.content_type)
        if target is not None:
            target.append({"title": entry.title, "content": entry.content})

    if entries:
        log.info(
            f"Loaded {len(entries)} homebrew entries for campaign '{ctx.campaign_name}': "
            f"{len(ctx.npcs)} NPCs, {len(ctx.locations)} locations, "
            f"{len(ctx.lore)} lore, {len(ctx.rules)} rules, {len(ctx.items)} items"
        )

    return ctx
