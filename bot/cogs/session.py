import logging

import discord
from discord.ext import commands

from bot.ui.embeds import session_started_embed, session_stopped_embed
from bot.voice.recorder import recorder

log = logging.getLogger(__name__)


class SessionCog(commands.Cog):
    """Session recording commands — join voice, capture audio, stop and save."""

    session = discord.SlashCommandGroup("session", "Manage D&D session recordings")

    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @session.command(description="Start recording the current voice channel")
    async def start(self, ctx: discord.ApplicationContext):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond("You need to be in a voice channel to start recording.", ephemeral=True)
            return

        voice_channel = ctx.author.voice.channel

        if recorder.is_recording(ctx.guild_id):
            await ctx.respond("Already recording in this server! Use `/session stop` first.", ephemeral=True)
            return

        await ctx.defer()

        try:
            await recorder.start_recording(voice_channel)
        except Exception as e:
            log.error(f"Failed to start recording: {e}")
            await ctx.followup.send(f"Failed to start recording: {e}", ephemeral=True)
            return

        embed = session_started_embed(
            channel_name=voice_channel.name,
            started_by=ctx.author.display_name,
            participant_count=len(voice_channel.members),
        )
        await ctx.followup.send(embed=embed)
        log.info(f"Session started by {ctx.author} in {voice_channel.name}")

    @session.command(description="Stop the current recording session")
    async def stop(self, ctx: discord.ApplicationContext):
        if not recorder.is_recording(ctx.guild_id):
            await ctx.respond("No active recording in this server.", ephemeral=True)
            return

        await ctx.defer()

        try:
            audio_data = await recorder.stop_recording(ctx.guild_id)
        except Exception as e:
            log.error(f"Failed to stop recording: {e}")
            await ctx.followup.send(f"Failed to stop recording: {e}", ephemeral=True)
            return

        # In Phase 2+, this is where we'd upload to S3 and kick off the pipeline
        total_bytes = sum(buf.getbuffer().nbytes for buf in audio_data.values())
        log.info(f"Captured {total_bytes / 1024:.1f} KB of audio from {len(audio_data)} user(s)")

        embed = session_stopped_embed(
            duration_seconds=0,  # Will be accurate once we track sink duration properly
            user_count=len(audio_data),
        )
        await ctx.followup.send(embed=embed)

    @session.command(description="Check if a recording is active")
    async def status(self, ctx: discord.ApplicationContext):
        if recorder.is_recording(ctx.guild_id):
            await ctx.respond("A session is currently being recorded. Use `/session stop` to end it.")
        else:
            await ctx.respond("No active recording. Use `/session start` to begin.")


def setup(bot: discord.Bot):
    bot.add_cog(SessionCog(bot))
