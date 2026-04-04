import asyncio
import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands
from sqlalchemy import select

from sqlalchemy import func

from bot.ui.embeds import session_started_embed, session_stopped_embed
from bot.voice.recorder import recorder
from core.db import async_session
from core.models.campaign import Campaign
from core.models.session import Session
from core.services.session_processor import get_or_create_campaign, process_session_audio
from core.services.subscription import TIER_LIMITS, get_guild_subscription, get_limit

log = logging.getLogger(__name__)


async def safe_defer(ctx: discord.ApplicationContext) -> bool:
    """Defer the interaction, returning False if it already expired."""
    age = (datetime.now(timezone.utc) - ctx.interaction.created_at).total_seconds()
    if age > 2.5:
        log.warning(f"Dropping stale interaction for /{ctx.command.qualified_name} (age={age:.1f}s)")
        return False
    try:
        await ctx.defer()
        return True
    except discord.NotFound:
        log.warning(f"Interaction expired before defer for /{ctx.command.qualified_name}")
        return False


async def safe_send(ctx: discord.ApplicationContext, *args, **kwargs):
    """Send a followup, falling back to channel message if interaction expired."""
    try:
        await ctx.followup.send(*args, **kwargs)
    except discord.NotFound:
        kwargs.pop("ephemeral", None)
        await ctx.channel.send(*args, **kwargs)


class SessionCog(commands.Cog):
    """Session recording commands — join voice, capture audio, stop and save."""

    session = discord.SlashCommandGroup("session", "Manage D&D session recordings")

    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @session.command(description="Start recording the current voice channel")
    async def start(self, ctx: discord.ApplicationContext):
        if not await safe_defer(ctx):
            return

        if not ctx.author.voice or not ctx.author.voice.channel:
            await safe_send(ctx, "You need to be in a voice channel to start recording.")
            return

        voice_channel = ctx.author.voice.channel

        if recorder.is_recording(ctx.guild_id):
            await safe_send(ctx, "Already recording in this server! Use `/session stop` first.")
            return

        # Check SERVER subscription tier and enforce limits
        limits = TIER_LIMITS["free"]
        tier_name = "Apprentice"
        try:
            limits, tier_name = await get_guild_subscription(ctx.guild_id)
            log.info(f"Server subscription for guild {ctx.guild_id}: {tier_name}")

            # Check sessions per month limit (per server, not per user)
            session_limit = get_limit(limits, "sessions_per_month")
            if session_limit is not None:
                campaign_id = await get_or_create_campaign(ctx.guild_id, ctx.author.id)
                first_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                async with async_session() as db:
                    result = await db.execute(
                        select(func.count(Session.id))
                        .join(Campaign, Session.campaign_id == Campaign.id)
                        .where(
                            Campaign.guild_id == ctx.guild_id,
                            Session.created_at >= first_of_month,
                        )
                    )
                    sessions_this_month = result.scalar() or 0

                if sessions_this_month >= session_limit:
                    await safe_send(
                        ctx,
                        f"This server has used all **{session_limit}** sessions this month on the **{tier_name}** tier. "
                        f"Upgrade at tavernrecap.com for more sessions!"
                    )
                    return
        except Exception:
            log.exception("Failed to check subscription — allowing session")

        try:
            await recorder.start_recording(voice_channel)
        except Exception as e:
            log.exception(f"Failed to start recording in {voice_channel.name}")
            await safe_send(ctx, f"Failed to start recording: {e}")
            return

        embed = session_started_embed(
            channel_name=voice_channel.name,
            started_by=ctx.author.display_name,
            participant_count=len(voice_channel.members),
        )
        await safe_send(ctx, embed=embed)
        log.info(f"Session started by {ctx.author} in {voice_channel.name}")

    @session.command(description="Stop the current recording session")
    async def stop(self, ctx: discord.ApplicationContext):
        if not await safe_defer(ctx):
            if recorder.is_recording(ctx.guild_id):
                await self._stop_and_process(ctx.guild_id, ctx.author.id, ctx.guild, ctx.channel)
            return

        if not recorder.is_recording(ctx.guild_id):
            await safe_send(ctx, "No active recording in this server.")
            return

        duration = recorder.get_duration(ctx.guild_id)
        voice_channel_id = recorder.get_channel_id(ctx.guild_id)

        try:
            audio_data = await recorder.stop_recording(ctx.guild_id)
        except Exception as e:
            log.error(f"Failed to stop recording: {e}")
            await safe_send(ctx, f"Failed to stop recording: {e}")
            return

        total_bytes = sum(buf.getbuffer().nbytes for buf in audio_data.values())
        log.info(f"Captured {total_bytes / 1024:.1f} KB of audio from {len(audio_data)} user(s)")

        embed = session_stopped_embed(
            duration_seconds=duration,
            user_count=len(audio_data),
        )
        await safe_send(ctx, embed=embed)

        await self._launch_processing(
            guild=ctx.guild,
            voice_channel_id=voice_channel_id,
            started_by=ctx.author.id,
            duration=duration,
            audio_data=audio_data,
            channel=ctx.channel,
        )

    async def _stop_and_process(
        self,
        guild_id: int,
        started_by: int,
        guild: discord.Guild,
        channel: discord.TextChannel,
    ):
        """Stop recording and process even when the interaction expired."""
        voice_channel_id = recorder.get_channel_id(guild_id)
        duration = recorder.get_duration(guild_id)
        audio_data = await recorder.stop_recording(guild_id)

        total_bytes = sum(buf.getbuffer().nbytes for buf in audio_data.values())
        log.info(f"Captured {total_bytes / 1024:.1f} KB of audio from {len(audio_data)} user(s)")

        embed = session_stopped_embed(duration_seconds=duration, user_count=len(audio_data))
        await channel.send(embed=embed)

        await self._launch_processing(
            guild=guild,
            voice_channel_id=voice_channel_id,
            started_by=started_by,
            duration=duration,
            audio_data=audio_data,
            channel=channel,
        )

    async def _launch_processing(
        self,
        guild: discord.Guild,
        voice_channel_id: int | None,
        started_by: int,
        duration: float,
        audio_data: dict,
        channel: discord.TextChannel,
    ):
        """Resolve campaign + user names, then fire background transcription task."""
        # Build user_names mapping, filtering out bots (music bots, etc.)
        user_names = {}
        for user_id in list(audio_data.keys()):
            member = guild.get_member(user_id)
            if member and member.bot:
                audio_data.pop(user_id)
                log.info(f"Filtered out bot: {member.display_name} ({user_id})")
                continue
            user_names[user_id] = member.display_name if member else f"User-{user_id}"

        # Get or create campaign for this guild
        try:
            campaign_id = await get_or_create_campaign(guild.id, started_by)
        except Exception:
            log.exception("Failed to resolve campaign — skipping transcription")
            await channel.send("Could not connect to the database. Transcription skipped.")
            return

        # Resolve output destination from campaign settings
        output_channel = channel
        create_thread = False
        try:
            async with async_session() as db:
                result = await db.execute(
                    select(Campaign).where(Campaign.id == campaign_id)
                )
                campaign = result.scalar_one_or_none()
                if campaign and campaign.summary_channel_id:
                    resolved = guild.get_channel(campaign.summary_channel_id)
                    if resolved:
                        output_channel = resolved
                if campaign and campaign.summary_mode == "thread":
                    create_thread = True
        except Exception:
            log.warning("Failed to load campaign settings — using default channel")

        # Look up tier limits for this server
        tier_limits = TIER_LIMITS["free"]
        try:
            tier_limits, _ = await get_guild_subscription(guild.id)
        except Exception:
            log.warning("Failed to look up server tier — using free limits")

        asyncio.create_task(
            process_session_audio(
                guild_id=guild.id,
                voice_channel_id=voice_channel_id or 0,
                started_by=started_by,
                campaign_id=campaign_id,
                duration_seconds=duration,
                audio_data=audio_data,
                user_names=user_names,
                channel=output_channel,
                create_thread=create_thread,
                tier_limits=tier_limits,
            )
        )
        log.info(f"Background transcription task launched for guild {guild.id}")

    @session.command(description="Check if a recording is active")
    async def status(self, ctx: discord.ApplicationContext):
        if not await safe_defer(ctx):
            return

        if recorder.is_recording(ctx.guild_id):
            duration = recorder.get_duration(ctx.guild_id)
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            await safe_send(ctx, f"Recording in progress — {minutes}m {seconds}s so far. Use `/session stop` to end it.")
        else:
            await safe_send(ctx, "No active recording. Use `/session start` to begin.")


def setup(bot: discord.Bot):
    bot.add_cog(SessionCog(bot))
