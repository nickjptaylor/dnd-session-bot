import logging

import discord
from discord.ext import commands
from sqlalchemy import select

from core.db import async_session
from core.models.user_link import UserLink
from core.services.subscription import check_subscription

log = logging.getLogger(__name__)


class AccountCog(commands.Cog):
    """Account linking and subscription commands."""

    account = discord.SlashCommandGroup("account", "Manage your Tavern Recap account")

    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @account.command(description="Link your Discord to your tavernrecap.com account")
    async def link(self, ctx: discord.ApplicationContext, email: str):
        await ctx.defer(ephemeral=True)

        # Check subscription via Lovable edge function
        sub = await check_subscription(email)

        async with async_session() as db:
            # Check if already linked
            result = await db.execute(
                select(UserLink).where(UserLink.discord_user_id == ctx.author.id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing link
                existing.email = email
                existing.stripe_product_id = sub.product_id
                existing.subscription_tier = sub.tier_name.lower().replace(" ", "_")
            else:
                # Create new link
                link = UserLink(
                    discord_user_id=ctx.author.id,
                    email=email,
                    stripe_product_id=sub.product_id,
                    subscription_tier=sub.tier_name.lower().replace(" ", "_"),
                )
                db.add(link)

            await db.commit()

        embed = discord.Embed(
            title="Account Linked",
            description=f"Connected to **{email}**",
            color=discord.Color.green(),
        )
        embed.add_field(name="Current Tier", value=sub.tier_name, inline=True)

        limits = sub.limits
        if limits["sessions_per_month"] == 0 and sub.tier_name == "Guild Master":
            embed.add_field(name="Sessions/Month", value="Unlimited", inline=True)
        else:
            embed.add_field(name="Sessions/Month", value=str(limits["sessions_per_month"]), inline=True)

        if limits["portraits_per_session"] == 0 and sub.tier_name == "Guild Master":
            embed.add_field(name="Portraits", value="Unlimited", inline=True)
        elif limits["portraits_per_session"] == 0:
            embed.add_field(name="Portraits", value="None", inline=True)
        else:
            embed.add_field(name="Portraits", value=str(limits["portraits_per_session"]), inline=True)

        embed.set_footer(text="Your tier is refreshed each time you start a session")
        await ctx.followup.send(embed=embed, ephemeral=True)
        log.info(f"User {ctx.author} linked to {email} ({sub.tier_name})")

    @account.command(description="Check your current subscription tier")
    async def status(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)

        async with async_session() as db:
            result = await db.execute(
                select(UserLink).where(UserLink.discord_user_id == ctx.author.id)
            )
            link = result.scalar_one_or_none()

        if not link:
            embed = discord.Embed(
                title="No Account Linked",
                description="Use `/account link` with your tavernrecap.com email to connect your account.",
                color=discord.Color.orange(),
            )
            embed.add_field(name="Current Tier", value="Apprentice (Free)", inline=True)
            embed.add_field(name="Sessions/Month", value="1", inline=True)
            await ctx.followup.send(embed=embed, ephemeral=True)
            return

        # Refresh subscription info
        sub = await check_subscription(link.email)

        # Update cached tier
        async with async_session() as db:
            result = await db.execute(
                select(UserLink).where(UserLink.discord_user_id == ctx.author.id)
            )
            user_link = result.scalar_one()
            user_link.stripe_product_id = sub.product_id
            user_link.subscription_tier = sub.tier_name.lower().replace(" ", "_")
            await db.commit()

        embed = discord.Embed(
            title="Tavern Recap Account",
            description=f"Linked to **{link.email}**",
            color=discord.Color.green(),
        )
        embed.add_field(name="Tier", value=sub.tier_name, inline=True)

        limits = sub.limits
        if limits["sessions_per_month"] == 0 and sub.tier_name == "Guild Master":
            embed.add_field(name="Sessions/Month", value="Unlimited", inline=True)
        else:
            embed.add_field(name="Sessions/Month", value=str(limits["sessions_per_month"]), inline=True)

        dm_tips = "Yes" if limits["dm_tips"] else "No"
        embed.add_field(name="DM Coaching", value=dm_tips, inline=True)

        await ctx.followup.send(embed=embed, ephemeral=True)

    @account.command(description="Unlink your Discord from tavernrecap.com")
    async def unlink(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)

        async with async_session() as db:
            result = await db.execute(
                select(UserLink).where(UserLink.discord_user_id == ctx.author.id)
            )
            link = result.scalar_one_or_none()

            if not link:
                await ctx.followup.send("No account linked.", ephemeral=True)
                return

            await db.delete(link)
            await db.commit()

        await ctx.followup.send("Account unlinked. You're back to the free tier.", ephemeral=True)
        log.info(f"User {ctx.author} unlinked their account")


def setup(bot: discord.Bot):
    bot.add_cog(AccountCog(bot))
