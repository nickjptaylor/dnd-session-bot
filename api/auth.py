"""API authentication — verifies requests from Lovable frontend."""

import logging

from fastapi import Header, HTTPException

from bot.config import settings

log = logging.getLogger(__name__)


async def verify_api_key(x_bot_api_key: str = Header(..., alias="x-bot-api-key")):
    """Verify the shared API key between Lovable and the bot.

    This is a simple shared-secret approach. Lovable sends the same
    bot_api_key that the bot uses to call Supabase edge functions.
    """
    if not settings.bot_api_key:
        raise HTTPException(status_code=500, detail="Bot API key not configured")

    if x_bot_api_key != settings.bot_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return True
