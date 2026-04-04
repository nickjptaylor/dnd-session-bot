import logging

import discord
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.db import async_session
from core.models.campaign import Campaign
from core.models.session import Session
from core.models.summary import SessionSummary

log = logging.getLogger(__name__)


class SummaryCog(commands.Cog):
    """Session summary commands."""

    summary = discord.SlashCommandGroup("summary", "View session summaries")

    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @summary.command(description="View the last session summary")
    async def last(self, ctx: discord.ApplicationContext):
        await ctx.defer()

        async with async_session() as db:
            # Find the most recent completed session for this guild's campaign
            result = await db.execute(
                select(Campaign).where(Campaign.guild_id == ctx.guild_id).limit(1)
            )
            campaign = result.scalar_one_or_none()

            if not campaign:
                await ctx.followup.send("No campaigns found. Record a session first with `/session start`.")
                return

            result = await db.execute(
                select(Session)
                .where(Session.campaign_id == campaign.id, Session.status == "complete")
                .order_by(Session.created_at.desc())
                .limit(1)
            )
            session = result.scalar_one_or_none()

            if not session:
                await ctx.followup.send("No completed sessions yet. Record a session first with `/session start`.")
                return

            result = await db.execute(
                select(SessionSummary)
                .where(SessionSummary.session_id == session.id)
                .options(selectinload(SessionSummary.key_moments))
            )
            summary = result.scalar_one_or_none()

            if not summary:
                await ctx.followup.send("Session was recorded but hasn't been summarized yet. Make sure `ANTHROPIC_API_KEY` is set.")
                return

        # Send summary
        summary_embed = discord.Embed(
            title="Last Session Summary",
            description=summary.narrative_summary[:4000],
            color=discord.Color.gold(),
        )
        if session.title:
            summary_embed.title = session.title
        await ctx.followup.send(embed=summary_embed)

        # Send key moments if any
        if summary.key_moments:
            moments_embed = discord.Embed(
                title="Key Moments",
                color=discord.Color.purple(),
            )
            for km in summary.key_moments:
                timestamp = f"[{km.timestamp_in_session}] " if km.timestamp_in_session else ""
                moments_embed.add_field(
                    name=f"{timestamp}Moment",
                    value=km.description[:1024],
                    inline=False,
                )
            await ctx.followup.send(embed=moments_embed)

    @summary.command(description="View summary history for this campaign")
    async def history(self, ctx: discord.ApplicationContext):
        await ctx.defer()

        async with async_session() as db:
            result = await db.execute(
                select(Campaign).where(Campaign.guild_id == ctx.guild_id).limit(1)
            )
            campaign = result.scalar_one_or_none()

            if not campaign:
                await ctx.followup.send("No campaigns found.")
                return

            result = await db.execute(
                select(Session)
                .where(Session.campaign_id == campaign.id, Session.status == "complete")
                .order_by(Session.created_at.desc())
                .limit(10)
            )
            sessions = result.scalars().all()

            if not sessions:
                await ctx.followup.send("No completed sessions yet.")
                return

            # Load summaries for these sessions
            session_ids = [s.id for s in sessions]
            result = await db.execute(
                select(SessionSummary).where(SessionSummary.session_id.in_(session_ids))
            )
            summaries = {s.session_id: s for s in result.scalars().all()}

        embed = discord.Embed(
            title=f"Session History — {campaign.name}",
            color=discord.Color.gold(),
        )

        for i, session in enumerate(sessions, 1):
            summary = summaries.get(session.id)
            if summary:
                preview = summary.narrative_summary[:200]
                if len(summary.narrative_summary) > 200:
                    preview += "..."
            else:
                preview = "(No summary available)"

            date_str = session.created_at.strftime("%b %d, %Y") if session.created_at else "Unknown"
            embed.add_field(
                name=f"Session {i} — {date_str}",
                value=preview,
                inline=False,
            )

        await ctx.followup.send(embed=embed)


def setup(bot: discord.Bot):
    bot.add_cog(SummaryCog(bot))
