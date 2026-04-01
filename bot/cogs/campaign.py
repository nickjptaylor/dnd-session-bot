import logging

import discord
from discord.ext import commands
from sqlalchemy import select

from core.db import async_session
from core.models.campaign import Campaign

log = logging.getLogger(__name__)


class CampaignCog(commands.Cog):
    """Campaign management commands."""

    campaign = discord.SlashCommandGroup("campaign", "Manage your D&D campaigns")

    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @campaign.command(description="Create a new campaign for this server")
    async def create(self, ctx: discord.ApplicationContext, name: str, description: str = ""):
        await ctx.defer()

        async with async_session() as db:
            campaign = Campaign(
                name=name,
                description=description or None,
                guild_id=ctx.guild_id,
                created_by_discord_id=ctx.author.id,
            )
            db.add(campaign)
            await db.commit()

        embed = discord.Embed(
            title="Campaign Created",
            description=f"**{name}**",
            color=discord.Color.gold(),
        )
        if description:
            embed.add_field(name="Description", value=description, inline=False)
        embed.set_footer(text="Sessions will be tracked under this campaign")
        await ctx.followup.send(embed=embed)
        log.info(f"Campaign '{name}' created by {ctx.author} in guild {ctx.guild_id}")

    @campaign.command(description="List campaigns in this server")
    async def list(self, ctx: discord.ApplicationContext):
        await ctx.defer()

        async with async_session() as db:
            result = await db.execute(
                select(Campaign).where(Campaign.guild_id == ctx.guild_id)
            )
            campaigns = result.scalars().all()

        if not campaigns:
            await ctx.followup.send("No campaigns yet. Use `/campaign create` to start one.")
            return

        embed = discord.Embed(
            title="Campaigns",
            color=discord.Color.gold(),
        )
        for c in campaigns:
            desc = c.description or "No description"
            embed.add_field(name=c.name, value=desc, inline=False)

        await ctx.followup.send(embed=embed)


def setup(bot: discord.Bot):
    bot.add_cog(CampaignCog(bot))
