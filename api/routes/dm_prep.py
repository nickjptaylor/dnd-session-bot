"""DM Prep API — thread tracking, session intros, and plot hook suggestions."""

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from api.auth import verify_api_key
from bot.config import settings
from core.db import async_session
from core.models.campaign import Campaign
from core.models.character import Character
from core.models.dm_prep import PlotHook, SessionIntro, StoryThread
from core.models.session import Session
from core.models.summary import SessionSummary
from core.services.campaign_context import build_campaign_context
from core.services.dm_prep import CharacterInfo, HookSuggester, IntroGenerator, ThreadExtractor

log = logging.getLogger(__name__)
router = APIRouter()


# ──────────────────────────────────────────────
# Response / Request schemas
# ──────────────────────────────────────────────

class ThreadResponse(BaseModel):
    id: str
    title: str
    description: str
    thread_type: str
    status: str
    source_session_id: str | None
    resolved_session_id: str | None
    created_at: str


class CampaignThreadsResponse(BaseModel):
    campaign_id: str
    threads: list[ThreadResponse]
    total: int


class ThreadUpdateRequest(BaseModel):
    status: str  # "active", "resolved", "dismissed"


class IntroResponse(BaseModel):
    id: str
    generated_text: str
    created_at: str


class CampaignIntrosResponse(BaseModel):
    campaign_id: str
    intros: list[IntroResponse]


class GenerateIntroRequest(BaseModel):
    num_sessions: int = 3  # How many recent sessions to use as context


class HookResponse(BaseModel):
    id: str
    title: str
    description: str
    hook_type: str | None
    status: str
    source_thread_id: str | None
    created_at: str


class CampaignHooksResponse(BaseModel):
    campaign_id: str
    hooks: list[HookResponse]


class HookUpdateRequest(BaseModel):
    status: str  # "pinned", "dismissed", "used"


class ThreadExtractionResponse(BaseModel):
    new_threads: int
    resolved_threads: int
    threads: list[ThreadResponse]


class PrepAllResponse(BaseModel):
    intro: IntroResponse | None
    hooks: list[HookResponse]
    threads: list[ThreadResponse]


# ──────────────────────────────────────────────
# Thread endpoints
# ──────────────────────────────────────────────

@router.get("/threads/campaign/{campaign_id}", response_model=CampaignThreadsResponse)
async def get_campaign_threads(
    campaign_id: UUID,
    status: str | None = Query(None, description="Filter by status: active, resolved, dismissed"),
    _auth: bool = Depends(verify_api_key),
):
    """List story threads for a campaign, optionally filtered by status."""
    async with async_session() as db:
        query = select(StoryThread).where(StoryThread.campaign_id == campaign_id)
        if status:
            query = query.where(StoryThread.status == status)
        query = query.order_by(StoryThread.created_at.desc())

        result = await db.execute(query)
        threads = result.scalars().all()

    return CampaignThreadsResponse(
        campaign_id=str(campaign_id),
        threads=[_thread_to_response(t) for t in threads],
        total=len(threads),
    )


@router.patch("/threads/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: UUID,
    request: ThreadUpdateRequest,
    _auth: bool = Depends(verify_api_key),
):
    """Update a thread's status (resolve, dismiss, reactivate)."""
    valid_statuses = {"active", "resolved", "dismissed"}
    if request.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {valid_statuses}")

    async with async_session() as db:
        result = await db.execute(select(StoryThread).where(StoryThread.id == thread_id))
        thread = result.scalar_one_or_none()
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        thread.status = request.status
        await db.commit()
        await db.refresh(thread)

    return _thread_to_response(thread)


@router.post("/threads/extract/{session_id}", response_model=ThreadExtractionResponse)
async def extract_threads(
    session_id: UUID,
    _auth: bool = Depends(verify_api_key),
):
    """Extract story threads from a session's summary using Claude."""
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="AI service not configured")

    async with async_session() as db:
        # Load session + summary
        result = await db.execute(
            select(Session).where(Session.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        result = await db.execute(
            select(SessionSummary).where(SessionSummary.session_id == session_id)
        )
        summary = result.scalar_one_or_none()
        if not summary:
            raise HTTPException(status_code=400, detail="Session has no summary yet")

        # Load existing active threads
        result = await db.execute(
            select(StoryThread).where(
                StoryThread.campaign_id == session.campaign_id,
                StoryThread.status == "active",
            )
        )
        existing = result.scalars().all()

    existing_threads = [
        {"id": str(t.id), "title": t.title, "description": t.description}
        for t in existing
    ]

    # Load campaign context
    world = await build_campaign_context(session.campaign_id)

    extractor = ThreadExtractor(api_key=settings.anthropic_api_key)
    extracted = await extractor.extract(
        summary=summary.narrative_summary,
        existing_threads=existing_threads,
        campaign_name=world.campaign_name,
        homebrew_context=world.format_for_prompt() if world.has_homebrew else None,
    )

    # Save results
    new_count = 0
    resolved_count = 0
    saved_threads = []

    async with async_session() as db:
        for thread in extracted:
            if thread.is_new:
                st = StoryThread(
                    campaign_id=session.campaign_id,
                    source_session_id=session_id,
                    title=thread.title,
                    description=thread.description,
                    thread_type=thread.thread_type,
                    status="active",
                )
                db.add(st)
                await db.flush()
                saved_threads.append(st)
                new_count += 1
            elif thread.existing_thread_id and thread.resolved:
                result = await db.execute(
                    select(StoryThread).where(StoryThread.id == thread.existing_thread_id)
                )
                existing_thread = result.scalar_one_or_none()
                if existing_thread:
                    existing_thread.status = "resolved"
                    existing_thread.resolved_session_id = session_id
                    saved_threads.append(existing_thread)
                    resolved_count += 1

        await db.commit()
        for t in saved_threads:
            await db.refresh(t)

    return ThreadExtractionResponse(
        new_threads=new_count,
        resolved_threads=resolved_count,
        threads=[_thread_to_response(t) for t in saved_threads],
    )


# ──────────────────────────────────────────────
# Intro endpoints
# ──────────────────────────────────────────────

@router.post("/intros/generate/{campaign_id}", response_model=IntroResponse)
async def generate_intro(
    campaign_id: UUID,
    request: GenerateIntroRequest | None = None,
    _auth: bool = Depends(verify_api_key),
):
    """Generate a session intro using Claude based on recent sessions."""
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="AI service not configured")

    num_sessions = request.num_sessions if request else 3
    num_sessions = min(num_sessions, 5)

    async with async_session() as db:
        # Verify campaign exists
        result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # Load recent completed sessions with summaries
        result = await db.execute(
            select(Session)
            .where(Session.campaign_id == campaign_id, Session.status == "complete")
            .order_by(Session.created_at.desc())
            .limit(num_sessions)
        )
        sessions = result.scalars().all()

        if not sessions:
            raise HTTPException(status_code=400, detail="No completed sessions to base intro on")

        # Load summaries for those sessions
        session_ids = [s.id for s in sessions]
        result = await db.execute(
            select(SessionSummary).where(SessionSummary.session_id.in_(session_ids))
        )
        summaries = {s.session_id: s for s in result.scalars().all()}

        # Build summaries list (oldest first for narrative flow)
        recent_summaries = []
        for session in reversed(sessions):
            if session.id in summaries:
                recent_summaries.append(summaries[session.id].narrative_summary)

        if not recent_summaries:
            raise HTTPException(status_code=400, detail="No session summaries available")

        # Load active threads
        result = await db.execute(
            select(StoryThread).where(
                StoryThread.campaign_id == campaign_id,
                StoryThread.status == "active",
            )
        )
        threads = result.scalars().all()

        # Load characters
        result = await db.execute(
            select(Character).where(Character.campaign_id == campaign_id)
        )
        characters = result.scalars().all()

    active_threads = [
        {"id": str(t.id), "title": t.title, "description": t.description, "thread_type": t.thread_type}
        for t in threads
    ]

    char_info = [
        CharacterInfo(
            name=c.name,
            race=c.race,
            character_class=c.character_class,
            level=c.level,
            description=c.description,
        )
        for c in characters
    ]

    generator = IntroGenerator(api_key=settings.anthropic_api_key)
    intro_text = await generator.generate(
        recent_summaries=recent_summaries,
        active_threads=active_threads,
        characters=char_info,
        campaign_name=campaign.name,
        campaign_description=campaign.description,
    )

    # Save the intro
    async with async_session() as db:
        intro = SessionIntro(
            campaign_id=campaign_id,
            generated_text=intro_text,
            source_summary_ids=json.dumps([str(sid) for sid in session_ids]),
        )
        db.add(intro)
        await db.commit()
        await db.refresh(intro)

    return IntroResponse(
        id=str(intro.id),
        generated_text=intro.generated_text,
        created_at=intro.created_at.isoformat(),
    )


@router.get("/intros/campaign/{campaign_id}", response_model=CampaignIntrosResponse)
async def get_campaign_intros(
    campaign_id: UUID,
    _auth: bool = Depends(verify_api_key),
):
    """List previous intros for a campaign."""
    async with async_session() as db:
        result = await db.execute(
            select(SessionIntro)
            .where(SessionIntro.campaign_id == campaign_id)
            .order_by(SessionIntro.created_at.desc())
            .limit(20)
        )
        intros = result.scalars().all()

    return CampaignIntrosResponse(
        campaign_id=str(campaign_id),
        intros=[
            IntroResponse(
                id=str(i.id),
                generated_text=i.generated_text,
                created_at=i.created_at.isoformat(),
            )
            for i in intros
        ],
    )


# ──────────────────────────────────────────────
# Plot hook endpoints
# ──────────────────────────────────────────────

@router.post("/hooks/suggest/{campaign_id}", response_model=CampaignHooksResponse)
async def suggest_hooks(
    campaign_id: UUID,
    _auth: bool = Depends(verify_api_key),
):
    """Generate plot hook suggestions using Claude."""
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="AI service not configured")

    async with async_session() as db:
        # Verify campaign
        result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # Load active threads
        result = await db.execute(
            select(StoryThread).where(
                StoryThread.campaign_id == campaign_id,
                StoryThread.status == "active",
            )
        )
        threads = result.scalars().all()

        # Load characters
        result = await db.execute(
            select(Character).where(Character.campaign_id == campaign_id)
        )
        characters = result.scalars().all()

        # Load most recent summary
        result = await db.execute(
            select(SessionSummary)
            .join(Session, SessionSummary.session_id == Session.id)
            .where(Session.campaign_id == campaign_id, Session.status == "complete")
            .order_by(Session.created_at.desc())
            .limit(1)
        )
        latest_summary = result.scalar_one_or_none()

    active_threads = [
        {"id": str(t.id), "title": t.title, "description": t.description, "thread_type": t.thread_type}
        for t in threads
    ]

    char_info = [
        CharacterInfo(
            name=c.name,
            race=c.race,
            character_class=c.character_class,
            level=c.level,
            description=c.description,
        )
        for c in characters
    ]

    # Load campaign context for homebrew
    world = await build_campaign_context(campaign_id)

    suggester = HookSuggester(api_key=settings.anthropic_api_key)
    hooks = await suggester.suggest(
        active_threads=active_threads,
        characters=char_info,
        campaign_name=campaign.name,
        campaign_description=campaign.description,
        homebrew_context=world.format_for_prompt() if world.has_homebrew else None,
        recent_summary=latest_summary.narrative_summary if latest_summary else None,
    )

    # Save hooks
    saved = []
    async with async_session() as db:
        for hook in hooks:
            # Validate thread ID if provided
            thread_id = None
            if hook.related_thread_id:
                try:
                    thread_id = UUID(hook.related_thread_id) if isinstance(hook.related_thread_id, str) else None
                except ValueError:
                    thread_id = None

            ph = PlotHook(
                campaign_id=campaign_id,
                source_thread_id=thread_id,
                title=hook.title,
                description=hook.description,
                hook_type=hook.hook_type,
                status="suggested",
            )
            db.add(ph)
            await db.flush()
            saved.append(ph)

        await db.commit()
        for h in saved:
            await db.refresh(h)

    return CampaignHooksResponse(
        campaign_id=str(campaign_id),
        hooks=[_hook_to_response(h) for h in saved],
    )


@router.get("/hooks/campaign/{campaign_id}", response_model=CampaignHooksResponse)
async def get_campaign_hooks(
    campaign_id: UUID,
    status: str | None = Query(None, description="Filter by status: suggested, pinned, dismissed, used"),
    _auth: bool = Depends(verify_api_key),
):
    """List plot hooks for a campaign, optionally filtered by status."""
    async with async_session() as db:
        query = select(PlotHook).where(PlotHook.campaign_id == campaign_id)
        if status:
            query = query.where(PlotHook.status == status)
        query = query.order_by(PlotHook.created_at.desc())

        result = await db.execute(query)
        hooks = result.scalars().all()

    return CampaignHooksResponse(
        campaign_id=str(campaign_id),
        hooks=[_hook_to_response(h) for h in hooks],
    )


@router.patch("/hooks/{hook_id}", response_model=HookResponse)
async def update_hook(
    hook_id: UUID,
    request: HookUpdateRequest,
    _auth: bool = Depends(verify_api_key),
):
    """Update a hook's status (pin, dismiss, mark as used)."""
    valid_statuses = {"suggested", "pinned", "dismissed", "used"}
    if request.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {valid_statuses}")

    async with async_session() as db:
        result = await db.execute(select(PlotHook).where(PlotHook.id == hook_id))
        hook = result.scalar_one_or_none()
        if not hook:
            raise HTTPException(status_code=404, detail="Hook not found")

        hook.status = request.status
        await db.commit()
        await db.refresh(hook)

    return _hook_to_response(hook)


# ──────────────────────────────────────────────
# Prep all (convenience endpoint)
# ──────────────────────────────────────────────

@router.post("/prep/{campaign_id}", response_model=PrepAllResponse)
async def prep_next_session(
    campaign_id: UUID,
    _auth: bool = Depends(verify_api_key),
):
    """One-click DM prep: generate intro, extract threads, and suggest hooks."""
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="AI service not configured")

    # Generate intro
    intro_resp = None
    try:
        intro_resp = await generate_intro(campaign_id, GenerateIntroRequest(num_sessions=3), _auth=True)
    except HTTPException:
        log.warning("Could not generate intro (no sessions?)")

    # Extract threads from latest session
    threads = []
    async with async_session() as db:
        result = await db.execute(
            select(Session)
            .where(Session.campaign_id == campaign_id, Session.status == "complete")
            .order_by(Session.created_at.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none()

    if latest:
        try:
            extraction = await extract_threads(latest.id, _auth=True)
            threads = extraction.threads
        except HTTPException:
            log.warning("Could not extract threads")

    # If no new threads, load existing active ones
    if not threads:
        async with async_session() as db:
            result = await db.execute(
                select(StoryThread).where(
                    StoryThread.campaign_id == campaign_id,
                    StoryThread.status == "active",
                ).order_by(StoryThread.created_at.desc())
            )
            threads = [_thread_to_response(t) for t in result.scalars().all()]

    # Suggest hooks
    hooks = []
    try:
        hooks_resp = await suggest_hooks(campaign_id, _auth=True)
        hooks = hooks_resp.hooks
    except HTTPException:
        log.warning("Could not suggest hooks")

    return PrepAllResponse(
        intro=intro_resp,
        hooks=hooks,
        threads=threads,
    )


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _thread_to_response(t: StoryThread) -> ThreadResponse:
    return ThreadResponse(
        id=str(t.id),
        title=t.title,
        description=t.description,
        thread_type=t.thread_type,
        status=t.status,
        source_session_id=str(t.source_session_id) if t.source_session_id else None,
        resolved_session_id=str(t.resolved_session_id) if t.resolved_session_id else None,
        created_at=t.created_at.isoformat() if t.created_at else "",
    )


def _hook_to_response(h: PlotHook) -> HookResponse:
    return HookResponse(
        id=str(h.id),
        title=h.title,
        description=h.description,
        hook_type=h.hook_type,
        status=h.status,
        source_thread_id=str(h.source_thread_id) if h.source_thread_id else None,
        created_at=h.created_at.isoformat() if h.created_at else "",
    )
