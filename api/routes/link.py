"""Linking code API — generate and verify one-time codes for account connection."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import verify_api_key
from core.services.linking import generate_code, verify_code

log = logging.getLogger(__name__)
router = APIRouter()


class GenerateCodeRequest(BaseModel):
    email: str
    discord_user_id: int | None = None  # Optional: from Discord OAuth on the website


class GenerateCodeResponse(BaseModel):
    code: str
    expires_in_seconds: int


class VerifyCodeRequest(BaseModel):
    code: str
    discord_user_id: int
    guild_id: int


class VerifyCodeResponse(BaseModel):
    success: bool
    email: str | None = None
    tier_name: str | None = None
    message: str


class CheckStatusRequest(BaseModel):
    email: str


class CheckStatusResponse(BaseModel):
    linked: bool
    discord_user_id: int | None = None
    guild_id: int | None = None
    tier_name: str | None = None


@router.post("/generate", response_model=GenerateCodeResponse)
async def generate_linking_code(
    request: GenerateCodeRequest,
    _auth: bool = Depends(verify_api_key),
):
    """Generate a one-time linking code. Called by tavernrecap.com after user signs up."""
    code = generate_code(
        email=request.email,
        discord_user_id=request.discord_user_id,
    )

    return GenerateCodeResponse(
        code=code,
        expires_in_seconds=600,
    )


@router.post("/verify", response_model=VerifyCodeResponse)
async def verify_linking_code(
    request: VerifyCodeRequest,
    _auth: bool = Depends(verify_api_key),
):
    """Verify a linking code and create the account link. Called by the Discord bot."""
    result = verify_code(request.code, request.discord_user_id)

    if not result:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired code. Generate a new one at tavernrecap.com",
        )

    email = result["email"]

    # Check subscription and create the link
    from sqlalchemy import select

    from core.db import async_session
    from core.models.user_link import UserLink
    from core.services.subscription import check_subscription

    sub = await check_subscription(email)

    async with async_session() as db:
        # Check if already linked in this guild
        existing = await db.execute(
            select(UserLink).where(
                UserLink.discord_user_id == request.discord_user_id,
                UserLink.guild_id == request.guild_id,
            )
        )
        link = existing.scalar_one_or_none()

        if link:
            link.email = email
            link.stripe_product_id = sub.product_id
            link.subscription_tier = sub.tier_name.lower().replace(" ", "_")
        else:
            link = UserLink(
                discord_user_id=request.discord_user_id,
                guild_id=request.guild_id,
                email=email,
                stripe_product_id=sub.product_id,
                subscription_tier=sub.tier_name.lower().replace(" ", "_"),
            )
            db.add(link)

        await db.commit()

    log.info(f"Account linked: {email} -> Discord {request.discord_user_id} in guild {request.guild_id} ({sub.tier_name})")

    # Notify Lovable so the website updates in real time
    from core.services.lovable_callback import notify_link
    await notify_link(email=email, discord_user_id=request.discord_user_id, guild_id=request.guild_id)

    return VerifyCodeResponse(
        success=True,
        email=email,
        tier_name=sub.tier_name,
        message=f"Linked to {email} ({sub.tier_name}). This server now has {sub.tier_name} features!",
    )


@router.post("/check-status", response_model=CheckStatusResponse)
async def check_link_status(
    request: CheckStatusRequest,
    _auth: bool = Depends(verify_api_key),
):
    """Check if an email has been linked to a Discord account.

    Called by tavernrecap.com to poll after showing the linking code.
    When linked=True, the website can move to the next onboarding step.
    """
    from sqlalchemy import select

    from core.db import async_session
    from core.models.user_link import UserLink

    async with async_session() as db:
        result = await db.execute(
            select(UserLink).where(UserLink.email == request.email).limit(1)
        )
        link = result.scalar_one_or_none()

    if not link:
        return CheckStatusResponse(linked=False)

    return CheckStatusResponse(
        linked=True,
        discord_user_id=link.discord_user_id,
        guild_id=link.guild_id,
        tier_name=link.subscription_tier,
    )
