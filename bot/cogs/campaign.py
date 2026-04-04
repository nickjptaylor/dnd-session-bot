import logging

import discord
from discord.ext import commands
from sqlalchemy import func, select

from core.db import async_session
from core.models.campaign import Campaign, HomebrewContent

log = logging.getLogger(__name__)

CONTENT_TYPES = ["lore", "npc", "location", "rule", "item"]


class CampaignCog(commands.Cog):
    """Campaign management commands."""

    campaign = discord.SlashCommandGroup("campaign", "Manage your D&D campaigns")
    homebrew = campaign.create_subgroup("homebrew", "Manage homebrew campaign content")

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

    @campaign.command(description="Set where session summaries are posted for this campaign")
    async def setchannel(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.TextChannel = None,
        mode: discord.Option(str, "Post as messages or create a thread per session", choices=["channel", "thread"], default="channel") = "channel",
    ):
        await ctx.defer()

        async with async_session() as db:
            result = await db.execute(
                select(Campaign).where(Campaign.guild_id == ctx.guild_id).limit(1)
            )
            campaign = result.scalar_one_or_none()

            if not campaign:
                await ctx.followup.send("No campaign found. Create one first with `/campaign create`.")
                return

            campaign.summary_channel_id = channel.id if channel else None
            campaign.summary_mode = mode
            await db.commit()

        if mode == "thread":
            if channel:
                await ctx.followup.send(f"Each session will create a **new thread** in {channel.mention}.")
            else:
                await ctx.followup.send("Each session will create a **new thread** wherever `/session stop` is used.")
        else:
            if channel:
                await ctx.followup.send(f"Session summaries will be posted in {channel.mention}.")
            else:
                await ctx.followup.send("Session summaries will be posted wherever `/session stop` is used (default).")

    @campaign.command(description="Set who the Dungeon Master is for this campaign")
    async def setdm(
        self,
        ctx: discord.ApplicationContext,
        dm: discord.Option(discord.User, "The Dungeon Master for this campaign"),
    ):
        await ctx.defer()

        async with async_session() as db:
            result = await db.execute(
                select(Campaign).where(Campaign.guild_id == ctx.guild_id).limit(1)
            )
            campaign = result.scalar_one_or_none()

            if not campaign:
                await ctx.followup.send("No campaign found. Create one first with `/campaign create`.")
                return

            campaign.dm_discord_id = dm.id
            await db.commit()

        await ctx.followup.send(f"**{dm.display_name}** is now the DM for this campaign. Their speech will be treated as narration/NPCs in transcripts, and they'll receive DM coaching notes after each session.")
        log.info(f"DM set to {dm} (ID: {dm.id}) for campaign '{campaign.name}' in guild {ctx.guild_id}")

    # --- Homebrew content commands ---

    @homebrew.command(description="Add homebrew content to your campaign")
    async def add(
        self,
        ctx: discord.ApplicationContext,
        content_type: discord.Option(str, "Type of content", choices=CONTENT_TYPES),
        title: discord.Option(str, "Title (e.g. 'Bram Ironkettle', 'The Gilded Flagon')"),
        content: discord.Option(str, "Description — who/what is this, key details the bot should know"),
    ):
        await ctx.defer()

        async with async_session() as db:
            result = await db.execute(
                select(Campaign).where(Campaign.guild_id == ctx.guild_id).limit(1)
            )
            campaign = result.scalar_one_or_none()

            if not campaign:
                await ctx.followup.send("No campaign found. Create one first with `/campaign create`.")
                return

            entry = HomebrewContent(
                campaign_id=campaign.id,
                title=title,
                content=content,
                content_type=content_type,
            )
            db.add(entry)
            await db.commit()

        type_emoji = {"lore": "📜", "npc": "🧙", "location": "🏰", "rule": "📏", "item": "⚔️"}
        emoji = type_emoji.get(content_type, "📝")

        embed = discord.Embed(
            title=f"{emoji} Homebrew Added",
            color=discord.Color.dark_gold(),
        )
        embed.add_field(name="Type", value=content_type.capitalize(), inline=True)
        embed.add_field(name="Title", value=title, inline=True)
        embed.add_field(name="Content", value=content[:1024], inline=False)
        embed.set_footer(text="This will be included in future session summaries and coaching")
        await ctx.followup.send(embed=embed)
        log.info(f"Homebrew '{title}' ({content_type}) added to campaign '{campaign.name}' by {ctx.author}")

    @homebrew.command(name="list", description="List all homebrew content for this campaign")
    async def homebrew_list(
        self,
        ctx: discord.ApplicationContext,
        content_type: discord.Option(str, "Filter by type (optional)", choices=CONTENT_TYPES, required=False) = None,
    ):
        await ctx.defer()

        async with async_session() as db:
            result = await db.execute(
                select(Campaign).where(Campaign.guild_id == ctx.guild_id).limit(1)
            )
            campaign = result.scalar_one_or_none()

            if not campaign:
                await ctx.followup.send("No campaign found. Create one first with `/campaign create`.")
                return

            query = select(HomebrewContent).where(HomebrewContent.campaign_id == campaign.id)
            if content_type:
                query = query.where(HomebrewContent.content_type == content_type)
            query = query.order_by(HomebrewContent.content_type, HomebrewContent.title)

            result = await db.execute(query)
            entries = result.scalars().all()

        if not entries:
            filter_text = f" ({content_type})" if content_type else ""
            await ctx.followup.send(f"No homebrew content{filter_text} yet. Use `/campaign homebrew add` to add some!")
            return

        type_emoji = {"lore": "📜", "npc": "🧙", "location": "🏰", "rule": "📏", "item": "⚔️"}

        embed = discord.Embed(
            title=f"Homebrew Content — {campaign.name}",
            color=discord.Color.dark_gold(),
        )

        # Group by type
        current_type = None
        for entry in entries:
            emoji = type_emoji.get(entry.content_type, "📝")
            preview = entry.content[:100] + ("..." if len(entry.content) > 100 else "")
            embed.add_field(
                name=f"{emoji} {entry.title}",
                value=f"*{entry.content_type}* — {preview}",
                inline=False,
            )

        embed.set_footer(text=f"{len(entries)} item(s)")
        await ctx.followup.send(embed=embed)

    @homebrew.command(description="View full details of a homebrew entry")
    async def view(
        self,
        ctx: discord.ApplicationContext,
        title: discord.Option(str, "Title of the homebrew entry to view"),
    ):
        await ctx.defer()

        async with async_session() as db:
            result = await db.execute(
                select(Campaign).where(Campaign.guild_id == ctx.guild_id).limit(1)
            )
            campaign = result.scalar_one_or_none()

            if not campaign:
                await ctx.followup.send("No campaign found.")
                return

            result = await db.execute(
                select(HomebrewContent).where(
                    HomebrewContent.campaign_id == campaign.id,
                    func.lower(HomebrewContent.title) == title.lower(),
                )
            )
            entry = result.scalar_one_or_none()

        if not entry:
            await ctx.followup.send(f"No homebrew entry found with title **{title}**. Use `/campaign homebrew list` to see all entries.")
            return

        type_emoji = {"lore": "📜", "npc": "🧙", "location": "🏰", "rule": "📏", "item": "⚔️"}
        emoji = type_emoji.get(entry.content_type, "📝")

        embed = discord.Embed(
            title=f"{emoji} {entry.title}",
            description=entry.content[:4000],
            color=discord.Color.dark_gold(),
        )
        embed.add_field(name="Type", value=entry.content_type.capitalize(), inline=True)
        embed.set_footer(text=f"Created {entry.created_at.strftime('%b %d, %Y')}")
        await ctx.followup.send(embed=embed)

    @homebrew.command(description="Remove a homebrew entry from your campaign")
    async def remove(
        self,
        ctx: discord.ApplicationContext,
        title: discord.Option(str, "Title of the homebrew entry to remove"),
    ):
        await ctx.defer()

        async with async_session() as db:
            result = await db.execute(
                select(Campaign).where(Campaign.guild_id == ctx.guild_id).limit(1)
            )
            campaign = result.scalar_one_or_none()

            if not campaign:
                await ctx.followup.send("No campaign found.")
                return

            result = await db.execute(
                select(HomebrewContent).where(
                    HomebrewContent.campaign_id == campaign.id,
                    func.lower(HomebrewContent.title) == title.lower(),
                )
            )
            entry = result.scalar_one_or_none()

            if not entry:
                await ctx.followup.send(f"No homebrew entry found with title **{title}**.")
                return

            entry_title = entry.title
            entry_type = entry.content_type
            await db.delete(entry)
            await db.commit()

        await ctx.followup.send(f"Removed **{entry_title}** ({entry_type}) from the campaign.")
        log.info(f"Homebrew '{entry_title}' removed from campaign '{campaign.name}' by {ctx.author}")


def setup(bot: discord.Bot):
    bot.add_cog(CampaignCog(bot))
