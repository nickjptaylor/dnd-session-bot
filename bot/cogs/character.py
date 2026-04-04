import logging

import discord
from discord.ext import commands
from sqlalchemy import select

from bot.cogs.campaign import get_active_campaign_for_guild
from core.db import async_session
from core.models.campaign import Campaign
from core.models.character import Character, CharacterReference
from core.services.storage import get_storage

log = logging.getLogger(__name__)


class CharacterCog(commands.Cog):
    """Character management commands."""

    character = discord.SlashCommandGroup("character", "Manage your D&D characters")

    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @character.command(description="Register a character for this campaign")
    async def create(
        self,
        ctx: discord.ApplicationContext,
        name: str,
        race: str = "",
        character_class: str = "",
        level: int = 1,
        description: str = "",
    ):
        await ctx.defer()

        try:
            async with async_session() as db:
                # Get active campaign or create default
                campaign = await get_active_campaign_for_guild(ctx.guild_id)

                if not campaign:
                    campaign = Campaign(
                        name="Default Campaign",
                        description="Auto-created campaign",
                        guild_id=ctx.guild_id,
                        created_by_discord_id=ctx.author.id,
                        is_active=True,
                    )
                    db.add(campaign)
                    await db.flush()
                    log.info(f"Created campaign: {campaign.id}")
                else:
                    # Re-fetch in this session
                    result = await db.execute(select(Campaign).where(Campaign.id == campaign.id))
                    campaign = result.scalar_one()

                log.info(f"Using campaign: {campaign.id} ({campaign.name})")

                # Check if this user already has a character in this campaign
                result = await db.execute(
                    select(Character).where(
                        Character.campaign_id == campaign.id,
                        Character.discord_user_id == ctx.author.id,
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    await ctx.followup.send(
                        f"You already have **{existing.name}** registered in **{campaign.name}**. "
                        f"Use `/character update` to change details or `/character delete` to remove them."
                    )
                    return

                char = Character(
                    campaign_id=campaign.id,
                    discord_user_id=ctx.author.id,
                    name=name,
                    race=race or None,
                    character_class=character_class or None,
                    level=level,
                    description=description or None,
                )
                db.add(char)
                await db.commit()
                log.info(f"Character '{name}' saved with id={char.id} for user {ctx.author.id}")

            embed = discord.Embed(
                title="Character Registered",
                description=f"**{name}**",
                color=discord.Color.green(),
            )
            if race:
                embed.add_field(name="Race", value=race, inline=True)
            if character_class:
                embed.add_field(name="Class", value=character_class, inline=True)
            embed.add_field(name="Level", value=str(level), inline=True)
            if description:
                embed.add_field(name="Description", value=description, inline=False)
            embed.set_footer(text=f"Campaign: {campaign.name} · Use /character upload to add a reference image")
            await ctx.followup.send(embed=embed)

        except Exception as e:
            log.exception(f"Failed to create character '{name}'")
            await ctx.followup.send(f"Failed to create character: {e}")

    @character.command(description="Upload a reference image for your character")
    async def upload(
        self,
        ctx: discord.ApplicationContext,
        image: discord.Attachment,
    ):
        await ctx.defer()

        if not image.content_type or not image.content_type.startswith("image/"):
            await ctx.followup.send("Please upload an image file (PNG, JPG, etc.)")
            return

        campaign = await get_active_campaign_for_guild(ctx.guild_id)

        if not campaign:
            await ctx.followup.send("No campaign found. Use `/character create` first.")
            return

        async with async_session() as db:
            result = await db.execute(
                select(Character).where(
                    Character.campaign_id == campaign.id,
                    Character.discord_user_id == ctx.author.id,
                )
            )
            char = result.scalar_one_or_none()

            if not char:
                await ctx.followup.send("You don't have a character registered. Use `/character create` first.")
                return

            # Download the image from Discord
            image_bytes = await image.read()

            # Upload to S3
            s3_key = f"characters/{char.id}/reference/{image.filename}"
            try:
                storage = get_storage()
                storage.upload(s3_key, image_bytes, content_type=image.content_type)
            except Exception:
                log.exception("Failed to upload character reference to S3")
                await ctx.followup.send("Failed to upload image. Is the storage service running? (`docker compose up -d`)")
                return

            # Save reference in DB
            ref = CharacterReference(
                character_id=char.id,
                s3_key=s3_key,
                filename=image.filename,
                content_type=image.content_type,
            )
            db.add(ref)
            await db.commit()

        embed = discord.Embed(
            title="Reference Image Uploaded",
            description=f"Added reference for **{char.name}**",
            color=discord.Color.green(),
        )
        embed.set_image(url=image.url)
        await ctx.followup.send(embed=embed)

    @character.command(description="List characters in the current campaign")
    async def list(self, ctx: discord.ApplicationContext):
        await ctx.defer()

        campaign = await get_active_campaign_for_guild(ctx.guild_id)

        if not campaign:
            await ctx.followup.send("No campaign found. Use `/campaign create` to start one.")
            return

        async with async_session() as db:
            result = await db.execute(
                select(Character).where(Character.campaign_id == campaign.id)
            )
            characters = result.scalars().all()

        if not characters:
            await ctx.followup.send("No characters yet. Use `/character create` to register one.")
            return

        embed = discord.Embed(
            title=f"Party Members — {campaign.name}",
            color=discord.Color.green(),
        )
        for char in characters:
            member = ctx.guild.get_member(char.discord_user_id)
            player_name = member.display_name if member else f"User-{char.discord_user_id}"

            details = []
            if char.race:
                details.append(char.race)
            if char.character_class:
                details.append(char.character_class)
            if char.level:
                details.append(f"Level {char.level}")
            detail_str = " · ".join(details) if details else "No details"

            embed.add_field(
                name=f"{char.name} ({player_name})",
                value=detail_str,
                inline=False,
            )

        await ctx.followup.send(embed=embed)

    @character.command(description="View your character details")
    async def view(self, ctx: discord.ApplicationContext):
        await ctx.defer()

        campaign = await get_active_campaign_for_guild(ctx.guild_id)

        if not campaign:
            await ctx.followup.send("No campaign found.")
            return

        async with async_session() as db:
            result = await db.execute(
                select(Character).where(
                    Character.campaign_id == campaign.id,
                    Character.discord_user_id == ctx.author.id,
                )
            )
            char = result.scalar_one_or_none()

            if not char:
                await ctx.followup.send("You don't have a character registered. Use `/character create` first.")
                return

        embed = discord.Embed(
            title=char.name,
            color=discord.Color.green(),
        )
        if char.race:
            embed.add_field(name="Race", value=char.race, inline=True)
        if char.character_class:
            embed.add_field(name="Class", value=char.character_class, inline=True)
        if char.level:
            embed.add_field(name="Level", value=str(char.level), inline=True)
        if char.description:
            embed.add_field(name="Description", value=char.description, inline=False)
        embed.set_footer(text=f"Campaign: {campaign.name}")

        await ctx.followup.send(embed=embed)


def setup(bot: discord.Bot):
    bot.add_cog(CharacterCog(bot))
