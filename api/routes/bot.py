"""Bot info API — invite link, status, and guild info for Lovable."""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.auth import verify_api_key
from bot.config import settings

log = logging.getLogger(__name__)
router = APIRouter()

# Bot permissions:
# Send Messages (2048) + Embed Links (16384) + Attach Files (32768)
# + Read Message History (65536) + View Channels (1024)
# + Connect (1048576) + Speak (2097152)
BOT_PERMISSIONS = 3263488


class BotInfoResponse(BaseModel):
    invite_url: str
    client_id: str

class GuildStatusResponse(BaseModel):
    guild_id: int
    bot_present: bool
    has_subscription: bool
    tier_name: str
    sessions_this_month: int
    session_limit: int | None


@router.get("/info", response_model=BotInfoResponse)
async def get_bot_info():
    """Get bot invite URL — no auth required (public for the Add to Discord button)."""
    client_id = settings.discord_client_id
    invite_url = (
        f"https://discord.com/oauth2/authorize"
        f"?client_id={client_id}"
        f"&permissions={BOT_PERMISSIONS}"
        f"&scope=bot%20applications.commands"
    )
    return BotInfoResponse(invite_url=invite_url, client_id=client_id)


@router.get("/guild/{guild_id}/status", response_model=GuildStatusResponse)
async def get_guild_status(
    guild_id: int,
    _auth: bool = Depends(verify_api_key),
):
    """Check bot status in a guild — subscription tier, usage this month."""
    from datetime import datetime, timezone

    from sqlalchemy import func, select

    from core.db import async_session
    from core.models.campaign import Campaign
    from core.models.session import Session
    from core.services.subscription import get_guild_subscription, get_limit

    # Get subscription
    limits, tier_name = await get_guild_subscription(guild_id)
    has_subscription = tier_name != "Apprentice"

    # Count sessions this month
    first_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    async with async_session() as db:
        result = await db.execute(
            select(func.count(Session.id))
            .join(Campaign, Session.campaign_id == Campaign.id)
            .where(
                Campaign.guild_id == guild_id,
                Session.created_at >= first_of_month,
            )
        )
        sessions_this_month = result.scalar() or 0

    session_limit_val = get_limit(limits, "sessions_per_month")

    return GuildStatusResponse(
        guild_id=guild_id,
        bot_present=True,  # If this endpoint returns, bot has DB access for this guild
        has_subscription=has_subscription,
        tier_name=tier_name,
        sessions_this_month=sessions_this_month,
        session_limit=session_limit_val,
    )
