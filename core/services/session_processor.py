import io
import logging
import uuid
from datetime import datetime, timezone

import discord
from sqlalchemy import select

from bot.config import settings
from core.db import async_session
from core.models.campaign import Campaign
from core.models.session import Session, SessionRecording, Transcript
from core.services.transcription import DeepgramBatchTranscriber

log = logging.getLogger(__name__)


async def process_session_audio(
    guild_id: int,
    voice_channel_id: int,
    started_by: int,
    campaign_id: uuid.UUID,
    duration_seconds: float,
    audio_data: dict[int, io.BytesIO],
    user_names: dict[int, str],
    channel: discord.TextChannel | None = None,
) -> None:
    """Background task: transcribe per-user audio via Deepgram and save to DB.

    Called as an asyncio task after /session stop so the user gets an
    immediate response while processing runs in the background.
    """
    session_id = None

    try:
        async with async_session() as db:
            # Create Session row
            session = Session(
                campaign_id=campaign_id,
                status="processing",
                voice_channel_id=voice_channel_id,
                started_by_discord_id=started_by,
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
            )
            db.add(session)
            await db.flush()
            session_id = session.id

            # Create SessionRecording rows (S3 upload deferred to Phase 4+)
            for user_id, audio_buf in audio_data.items():
                audio_buf.seek(0)
                size_kb = len(audio_buf.getbuffer()) / 1024
                recording = SessionRecording(
                    session_id=session.id,
                    discord_user_id=user_id,
                    s3_key=f"recordings/{session.id}/{user_id}.wav",  # placeholder until S3 wired
                    duration_seconds=duration_seconds,
                    format="wav",
                )
                db.add(recording)
                log.info(f"Recorded {size_kb:.1f} KB from user {user_names.get(user_id, user_id)}")

            await db.commit()

        # Transcribe all users' audio in parallel via Deepgram
        log.info(f"Starting transcription for session {session_id} ({len(audio_data)} user(s))")

        transcriber = DeepgramBatchTranscriber(api_key=settings.deepgram_api_key)
        user_words = await transcriber.transcribe_users(audio_data)

        total_words = sum(len(words) for _, words in user_words)
        log.info(f"Transcription complete: {total_words} total words from {len(audio_data)} user(s)")

        # Merge into a single speaker-labelled transcript
        transcript_text = DeepgramBatchTranscriber.merge_transcripts(user_words, user_names)

        if not transcript_text:
            log.warning(f"Session {session_id}: no speech detected in any audio stream")
            transcript_text = "(No speech detected)"

        # Save transcript and update session status
        async with async_session() as db:
            transcript = Transcript(
                session_id=session_id,
                provider="deepgram",
                content=transcript_text,
                is_final=True,
            )
            db.add(transcript)

            result = await db.execute(select(Session).where(Session.id == session_id))
            session = result.scalar_one()
            session.status = "complete"

            await db.commit()

        log.info(f"Session {session_id} processing complete")

        # Notify the channel
        if channel:
            word_count = total_words
            embed = discord.Embed(
                title="Transcription Complete",
                description=f"Processed **{word_count}** words from **{len(audio_data)}** participant(s)",
                color=discord.Color.blue(),
            )
            # Show a preview of the transcript (first 500 chars)
            preview = transcript_text[:500]
            if len(transcript_text) > 500:
                preview += "..."
            embed.add_field(name="Preview", value=preview, inline=False)
            embed.set_footer(text="Full transcript saved — summaries coming in Phase 3")
            await channel.send(embed=embed)

    except Exception:
        log.exception(f"Failed to process session audio (session_id={session_id})")

        # Mark session as failed if we created one
        if session_id:
            try:
                async with async_session() as db:
                    result = await db.execute(select(Session).where(Session.id == session_id))
                    session = result.scalar_one()
                    session.status = "failed"
                    await db.commit()
            except Exception:
                log.exception("Failed to mark session as failed")

        if channel:
            await channel.send("Something went wrong processing the session audio. Check the logs for details.")


async def get_or_create_campaign(guild_id: int, created_by: int) -> uuid.UUID:
    """Get the campaign for a guild, or auto-create a default one."""
    async with async_session() as db:
        result = await db.execute(
            select(Campaign).where(Campaign.guild_id == guild_id).limit(1)
        )
        campaign = result.scalar_one_or_none()

        if campaign:
            return campaign.id

        # Auto-create a default campaign
        campaign = Campaign(
            name="Default Campaign",
            description="Auto-created campaign for session tracking",
            guild_id=guild_id,
            created_by_discord_id=created_by,
        )
        db.add(campaign)
        await db.commit()
        await db.refresh(campaign)
        log.info(f"Auto-created default campaign for guild {guild_id}")
        return campaign.id
