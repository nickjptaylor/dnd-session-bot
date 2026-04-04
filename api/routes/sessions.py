"""Session history API — serves session data to Lovable web dashboard."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from api.auth import verify_api_key
from core.db import async_session
from core.models.campaign import Campaign
from core.models.session import Session
from core.models.summary import GeneratedArt, KeyMoment, SessionSummary
from core.services.storage import get_storage

log = logging.getLogger(__name__)
router = APIRouter()


# --- Response schemas ---

class ArtResponse(BaseModel):
    s3_url: str | None
    provider: str
    prompt_used: str

class KeyMomentResponse(BaseModel):
    id: str
    description: str
    scene_prompt: str | None
    timestamp: str | None
    discord_user_id: int
    art: ArtResponse | None

class SummaryResponse(BaseModel):
    narrative_summary: str
    dm_coaching_notes: str | None
    key_moments: list[KeyMomentResponse]

class SessionResponse(BaseModel):
    id: str
    session_number: int | None
    title: str | None
    status: str
    started_at: str
    ended_at: str | None
    created_at: str

class SessionDetailResponse(SessionResponse):
    summary: SummaryResponse | None

class CampaignSessionsResponse(BaseModel):
    campaign_id: str
    campaign_name: str
    guild_id: int
    sessions: list[SessionResponse]
    total: int


# --- Endpoints ---

@router.get("/guild/{guild_id}", response_model=CampaignSessionsResponse)
async def get_guild_sessions(
    guild_id: int,
    limit: int = Query(20, le=50),
    offset: int = Query(0, ge=0),
    _auth: bool = Depends(verify_api_key),
):
    """Get session history for a guild's active campaign."""
    async with async_session() as db:
        # Find active campaign
        result = await db.execute(
            select(Campaign)
            .where(Campaign.guild_id == guild_id, Campaign.is_active == True)  # noqa: E712
            .limit(1)
        )
        campaign = result.scalar_one_or_none()

        if not campaign:
            # Fall back to any campaign
            result = await db.execute(
                select(Campaign)
                .where(Campaign.guild_id == guild_id)
                .order_by(Campaign.created_at.desc())
                .limit(1)
            )
            campaign = result.scalar_one_or_none()

        if not campaign:
            raise HTTPException(status_code=404, detail="No campaign found for this guild")

        # Count total sessions
        from sqlalchemy import func
        result = await db.execute(
            select(func.count(Session.id)).where(Session.campaign_id == campaign.id)
        )
        total = result.scalar() or 0

        # Get sessions
        result = await db.execute(
            select(Session)
            .where(Session.campaign_id == campaign.id)
            .order_by(Session.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        sessions = result.scalars().all()

    return CampaignSessionsResponse(
        campaign_id=str(campaign.id),
        campaign_name=campaign.name,
        guild_id=guild_id,
        sessions=[
            SessionResponse(
                id=str(s.id),
                session_number=s.session_number,
                title=s.title,
                status=s.status,
                started_at=s.started_at.isoformat() if s.started_at else "",
                ended_at=s.ended_at.isoformat() if s.ended_at else None,
                created_at=s.created_at.isoformat() if s.created_at else "",
            )
            for s in sessions
        ],
        total=total,
    )


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(
    session_id: UUID,
    _auth: bool = Depends(verify_api_key),
):
    """Get full session detail including summary, key moments, and art URLs."""
    storage = None
    try:
        storage = get_storage()
    except Exception:
        log.warning("S3 storage unavailable — art URLs will be empty")

    async with async_session() as db:
        result = await db.execute(
            select(Session).where(Session.id == session_id)
        )
        session = result.scalar_one_or_none()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Load summary with key moments and art
        result = await db.execute(
            select(SessionSummary)
            .where(SessionSummary.session_id == session_id)
            .options(
                selectinload(SessionSummary.key_moments).selectinload(KeyMoment.art)
            )
        )
        summary = result.scalar_one_or_none()

    summary_data = None
    if summary:
        moments = []
        for km in summary.key_moments:
            art_data = None
            if km.art:
                s3_url = None
                if storage:
                    try:
                        s3_url = storage.get_url(km.art.s3_key, expires_in=3600)
                    except Exception:
                        pass
                art_data = ArtResponse(
                    s3_url=s3_url,
                    provider=km.art.provider,
                    prompt_used=km.art.prompt_used,
                )

            moments.append(KeyMomentResponse(
                id=str(km.id),
                description=km.description,
                scene_prompt=km.scene_prompt,
                timestamp=km.timestamp_in_session,
                discord_user_id=km.discord_user_id,
                art=art_data,
            ))

        summary_data = SummaryResponse(
            narrative_summary=summary.narrative_summary,
            dm_coaching_notes=summary.dm_coaching_notes,
            key_moments=moments,
        )

    return SessionDetailResponse(
        id=str(session.id),
        session_number=session.session_number,
        title=session.title,
        status=session.status,
        started_at=session.started_at.isoformat() if session.started_at else "",
        ended_at=session.ended_at.isoformat() if session.ended_at else None,
        created_at=session.created_at.isoformat() if session.created_at else "",
        summary=summary_data,
    )
