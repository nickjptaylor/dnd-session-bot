"""Notify tavernrecap.com (Lovable/Supabase) when account links change.

Called after /account link and /account unlink so the website
updates in real time without polling.
"""

import logging

import httpx

from bot.config import settings

log = logging.getLogger(__name__)

CALLBACK_URL = f"{settings.tavern_recap_supabase_url}/functions/v1/bot-link-callback"


async def notify_link(email: str, discord_user_id: int, guild_id: int) -> None:
    """Tell Lovable that an account was linked."""
    await _send_callback({
        "email": email,
        "discord_user_id": str(discord_user_id),
        "guild_id": str(guild_id),
    })


async def notify_unlink(email: str, guild_id: int) -> None:
    """Tell Lovable that an account was unlinked."""
    await _send_callback({
        "action": "unlink",
        "email": email,
        "guild_id": str(guild_id),
    })


async def _send_callback(payload: dict) -> None:
    """Fire the callback to Supabase. Best-effort — don't fail the main operation."""
    headers = {"Content-Type": "application/json"}
    if settings.bot_api_key:
        headers["x-bot-api-key"] = settings.bot_api_key

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(CALLBACK_URL, json=payload, headers=headers)
            resp.raise_for_status()
        log.info(f"Lovable callback sent: {payload.get('action', 'link')} for {payload['email']}")
    except Exception:
        log.warning(f"Lovable callback failed (non-fatal): {payload}", exc_info=True)
