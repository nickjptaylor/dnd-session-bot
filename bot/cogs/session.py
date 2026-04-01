import logging

import discord
from discord.ext import commands

from bot.ui.embeds import session_started_embed, session_stopped_embed
from bot.voice.recorder import recorder

log = logging.getLogger(__name__)


async def safe_defer(ctx: discord.ApplicationContext) -> bool:
    """Defer the interaction, returning False if it already expired."""
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
        # Interaction expired — send as a regular channel message instead
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
            # Still stop the recording even if interaction expired
            if recorder.is_recording(ctx.guild_id):
                duration = recorder.get_duration(ctx.guild_id)
                audio_data = await recorder.stop_recording(ctx.guild_id)
                total_bytes = sum(buf.getbuffer().nbytes for buf in audio_data.values())
                log.info(f"Captured {total_bytes / 1024:.1f} KB of audio from {len(audio_data)} user(s)")
                embed = session_stopped_embed(duration_seconds=duration, user_count=len(audio_data))
                await ctx.channel.send(embed=embed)
            return

        if not recorder.is_recording(ctx.guild_id):
            await safe_send(ctx, "No active recording in this server.")
            return

        duration = recorder.get_duration(ctx.guild_id)

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
