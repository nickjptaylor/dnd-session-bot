"""Campaign API — serves campaign data to Lovable web dashboard."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from api.auth import verify_api_key
from core.db import async_session
from core.models.campaign import Campaign, HomebrewContent
from core.models.character import Character

log = logging.getLogger(__name__)
router = APIRouter()


# --- Response schemas ---

class CharacterResponse(BaseModel):
    id: str
    name: str
    race: str | None
    character_class: str | None
    level: int | None
    description: str | None
    discord_user_id: int

class HomebrewResponse(BaseModel):
    id: str
    title: str
    content: str
    content_type: str

class CampaignResponse(BaseModel):
    id: str
    name: str
    description: str | None
    guild_id: int
    is_active: bool
    dm_discord_id: int | None
    summary_mode: str
    created_at: str

class CampaignDetailResponse(CampaignResponse):
    characters: list[CharacterResponse]
    homebrew: list[HomebrewResponse]

class GuildCampaignsResponse(BaseModel):
    guild_id: int
    campaigns: list[CampaignResponse]


# --- Endpoints ---

@router.get("/guild/{guild_id}", response_model=GuildCampaignsResponse)
async def get_guild_campaigns(
    guild_id: int,
    _auth: bool = Depends(verify_api_key),
):
    """List all campaigns for a guild."""
    async with async_session() as db:
        result = await db.execute(
            select(Campaign)
            .where(Campaign.guild_id == guild_id)
            .order_by(Campaign.created_at)
        )
        campaigns = result.scalars().all()

    return GuildCampaignsResponse(
        guild_id=guild_id,
        campaigns=[
            CampaignResponse(
                id=str(c.id),
                name=c.name,
                description=c.description,
                guild_id=c.guild_id,
                is_active=c.is_active,
                dm_discord_id=c.dm_discord_id,
                summary_mode=c.summary_mode,
                created_at=c.created_at.isoformat() if c.created_at else "",
            )
            for c in campaigns
        ],
    )


@router.get("/{campaign_id}", response_model=CampaignDetailResponse)
async def get_campaign_detail(
    campaign_id: str,
    _auth: bool = Depends(verify_api_key),
):
    """Get full campaign detail with characters and homebrew."""
    async with async_session() as db:
        result = await db.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # Load characters
        result = await db.execute(
            select(Character).where(Character.campaign_id == campaign.id)
        )
        characters = result.scalars().all()

        # Load homebrew
        result = await db.execute(
            select(HomebrewContent)
            .where(HomebrewContent.campaign_id == campaign.id)
            .order_by(HomebrewContent.content_type, HomebrewContent.title)
        )
        homebrew = result.scalars().all()

    return CampaignDetailResponse(
        id=str(campaign.id),
        name=campaign.name,
        description=campaign.description,
        guild_id=campaign.guild_id,
        is_active=campaign.is_active,
        dm_discord_id=campaign.dm_discord_id,
        summary_mode=campaign.summary_mode,
        created_at=campaign.created_at.isoformat() if campaign.created_at else "",
        characters=[
            CharacterResponse(
                id=str(ch.id),
                name=ch.name,
                race=ch.race,
                character_class=ch.character_class,
                level=ch.level,
                description=ch.description,
                discord_user_id=ch.discord_user_id,
            )
            for ch in characters
        ],
        homebrew=[
            HomebrewResponse(
                id=str(hb.id),
                title=hb.title,
                content=hb.content,
                content_type=hb.content_type,
            )
            for hb in homebrew
        ],
    )
