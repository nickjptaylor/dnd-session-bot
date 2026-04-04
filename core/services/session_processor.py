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
from core.models.summary import KeyMoment, SessionSummary
from core.services.dm_coach import DMCoach
from core.services.key_moments import KeyMomentExtractor
from core.services.summarizer import CharacterContext, SessionSummarizer
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
    create_thread: bool = False,
) -> None:
    """Background task: transcribe, summarize, extract key moments, and coach.

    Called as an asyncio task after /session stop so the user gets an
    immediate response while processing runs in the background.
    If create_thread is True, a new thread is created in the channel for output.
    """
    session_id = None

    try:
        # --- Stage 1: Create session + recording rows ---
        async with async_session() as db:
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

            for user_id, audio_buf in audio_data.items():
                audio_buf.seek(0)
                size_kb = len(audio_buf.getbuffer()) / 1024
                recording = SessionRecording(
                    session_id=session.id,
                    discord_user_id=user_id,
                    s3_key=f"recordings/{session.id}/{user_id}.wav",
                    duration_seconds=duration_seconds,
                    format="wav",
                )
                db.add(recording)
                log.info(f"Recorded {size_kb:.1f} KB from user {user_names.get(user_id, user_id)}")

            await db.commit()

        # Create a thread for output if requested
        if create_thread and channel:
            try:
                date_str = datetime.now(timezone.utc).strftime("%b %d, %Y")
                thread = await channel.create_thread(
                    name=f"Session — {date_str}",
                    type=discord.ChannelType.public_thread,
                )
                channel = thread
                log.info(f"Created thread '{thread.name}' for session output")
            except Exception:
                log.warning("Failed to create thread — posting to channel instead")

        # --- Stage 2: Transcribe via Deepgram ---
        log.info(f"Starting transcription for session {session_id} ({len(audio_data)} user(s))")

        transcriber = DeepgramBatchTranscriber(api_key=settings.deepgram_api_key)
        user_words = await transcriber.transcribe_users(audio_data)

        total_words = sum(len(words) for _, words in user_words)
        log.info(f"Transcription complete: {total_words} total words")

        transcript_text = DeepgramBatchTranscriber.merge_transcripts(user_words, user_names)

        if not transcript_text:
            log.warning(f"Session {session_id}: no speech detected")
            transcript_text = "(No speech detected)"

        # Save transcript
        async with async_session() as db:
            transcript = Transcript(
                session_id=session_id,
                provider="deepgram",
                content=transcript_text,
                is_final=True,
            )
            db.add(transcript)
            await db.commit()

        if channel:
            embed = discord.Embed(
                title="Transcription Complete",
                description=f"Processed **{total_words}** words from **{len(audio_data)}** participant(s)",
                color=discord.Color.blue(),
            )
            preview = transcript_text[:500]
            if len(transcript_text) > 500:
                preview += "..."
            embed.add_field(name="Preview", value=preview, inline=False)
            embed.set_footer(text="Generating summary...")
            await channel.send(embed=embed)

        # --- Stage 3: Summarize, extract key moments, DM coaching ---
        if not settings.anthropic_api_key:
            log.warning("No ANTHROPIC_API_KEY set — skipping summarization")
            async with async_session() as db:
                result = await db.execute(select(Session).where(Session.id == session_id))
                s = result.scalar_one()
                s.status = "complete"
                await db.commit()
            return

        # Look up campaign info for context
        campaign_name = None
        campaign_description = None
        async with async_session() as db:
            result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
            campaign = result.scalar_one_or_none()
            if campaign:
                campaign_name = campaign.name
                campaign_description = campaign.description

        # Build character context from user_names (full Character records come in later phases)
        characters = [
            CharacterContext(
                name=name,
                player_name=name,
                discord_user_id=uid,
            )
            for uid, name in user_names.items()
        ]

        # 3a: Narrative summary
        log.info(f"Generating narrative summary for session {session_id}")
        summarizer = SessionSummarizer(api_key=settings.anthropic_api_key)
        narrative = await summarizer.summarize(
            transcript=transcript_text,
            characters=characters,
            campaign_name=campaign_name,
            campaign_description=campaign_description,
        )

        # 3b: Key moments
        log.info(f"Extracting key moments for session {session_id}")
        extractor = KeyMomentExtractor(api_key=settings.anthropic_api_key)
        moments = await extractor.extract(
            transcript=transcript_text,
            characters=characters,
        )

        # 3c: DM coaching
        log.info(f"Generating DM coaching notes for session {session_id}")
        coach = DMCoach(api_key=settings.anthropic_api_key)
        coaching_notes = await coach.coach(
            transcript=transcript_text,
            summary=narrative,
            campaign_name=campaign_name,
        )

        # --- Stage 4: Save everything to DB ---
        async with async_session() as db:
            summary = SessionSummary(
                session_id=session_id,
                narrative_summary=narrative,
                dm_coaching_notes=coaching_notes,
            )
            db.add(summary)
            await db.flush()

            for moment in moments:
                # Try to resolve discord_user_id from player_name
                discord_user_id = moment.discord_user_id
                if not discord_user_id:
                    for uid, name in user_names.items():
                        if name.lower() == moment.player_name.lower():
                            discord_user_id = uid
                            break

                km = KeyMoment(
                    summary_id=summary.id,
                    discord_user_id=discord_user_id or 0,
                    description=moment.description,
                    scene_prompt=moment.scene_prompt,
                    timestamp_in_session=moment.timestamp,
                )
                db.add(km)

            result = await db.execute(select(Session).where(Session.id == session_id))
            session = result.scalar_one()
            session.status = "complete"

            await db.commit()

        log.info(f"Session {session_id} fully processed")

        # --- Stage 5: Post results to Discord ---
        if channel:
            # Summary embed
            summary_embed = discord.Embed(
                title="Session Summary",
                description=narrative[:4000],  # Discord embed limit
                color=discord.Color.gold(),
            )
            if len(narrative) > 4000:
                summary_embed.set_footer(text="(Summary truncated — full version saved)")
            await channel.send(embed=summary_embed)

            # Key moments embed
            if moments:
                moments_embed = discord.Embed(
                    title="Key Moments",
                    color=discord.Color.purple(),
                )
                for m in moments:
                    timestamp = f"[{m.timestamp}] " if m.timestamp else ""
                    moments_embed.add_field(
                        name=f"{timestamp}{m.player_name}",
                        value=m.description[:1024],
                        inline=False,
                    )
                await channel.send(embed=moments_embed)

            # DM coaching (send as ephemeral-style DM to the session starter)
            if coaching_notes:
                coaching_embed = discord.Embed(
                    title="DM Coaching Notes",
                    description=coaching_notes[:4000],
                    color=discord.Color.teal(),
                )
                coaching_embed.set_footer(text="These notes are private — only you can see this DM")
                try:
                    guild = channel.guild
                    dm_user = guild.get_member(started_by)
                    if dm_user:
                        await dm_user.send(embed=coaching_embed)
                        log.info(f"Sent DM coaching notes to user {started_by}")
                    else:
                        log.warning(f"Could not find member {started_by} for DM coaching")
                except discord.Forbidden:
                    log.warning(f"Cannot DM user {started_by} — DMs may be disabled")
                except Exception:
                    log.exception(f"Failed to send DM coaching notes to {started_by}")

    except Exception:
        log.exception(f"Failed to process session (session_id={session_id})")

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
            await channel.send("Something went wrong processing the session. Check the logs for details.")


async def get_or_create_campaign(guild_id: int, created_by: int) -> uuid.UUID:
    """Get the campaign for a guild, or auto-create a default one."""
    async with async_session() as db:
        result = await db.execute(
            select(Campaign).where(Campaign.guild_id == guild_id).limit(1)
        )
        campaign = result.scalar_one_or_none()

        if campaign:
            return campaign.id

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
