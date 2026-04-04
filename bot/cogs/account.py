import logging

import discord
from discord.ext import commands
from sqlalchemy import select

from core.db import async_session
from core.models.user_link import UserLink
from core.services.subscription import check_subscription, get_guild_subscription

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
            # Check if already linked in this guild
            result = await db.execute(
                select(UserLink).where(
                    UserLink.discord_user_id == ctx.author.id,
                    UserLink.guild_id == ctx.guild_id,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing link
                existing.email = email
                existing.stripe_product_id = sub.product_id
                existing.subscription_tier = sub.tier_name.lower().replace(" ", "_")
            else:
                # Create new link for this guild
                link = UserLink(
                    discord_user_id=ctx.author.id,
                    guild_id=ctx.guild_id,
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
        embed.add_field(name="Your Tier", value=sub.tier_name, inline=True)

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

        embed.set_footer(text="Your subscription now covers this entire server!")
        await ctx.followup.send(embed=embed, ephemeral=True)
        log.info(f"User {ctx.author} linked to {email} ({sub.tier_name}) in guild {ctx.guild_id}")

    @account.command(description="Check this server's subscription tier")
    async def status(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)

        # Get the best subscription for this entire guild
        limits, tier_name = await get_guild_subscription(ctx.guild_id)

        # Also check if THIS user has a link
        async with async_session() as db:
            result = await db.execute(
                select(UserLink).where(
                    UserLink.discord_user_id == ctx.author.id,
                    UserLink.guild_id == ctx.guild_id,
                )
            )
            my_link = result.scalar_one_or_none()

        embed = discord.Embed(
            title="Server Subscription",
            color=discord.Color.green() if tier_name != "Apprentice" else discord.Color.orange(),
        )
        embed.add_field(name="Server Tier", value=tier_name, inline=True)

        from core.services.subscription import get_limit
        session_limit = get_limit(limits, "sessions_per_month")
        embed.add_field(
            name="Sessions/Month",
            value="Unlimited" if session_limit is None else str(session_limit),
            inline=True,
        )

        dm_tips = "Yes" if limits.get("dm_tips") else "No"
        embed.add_field(name="DM Coaching", value=dm_tips, inline=True)

        portraits = get_limit(limits, "portraits_per_session")
        embed.add_field(
            name="Portraits/Session",
            value="Unlimited" if portraits is None else str(portraits),
            inline=True,
        )

        if my_link:
            embed.set_footer(text=f"Your account: {my_link.email}")
        else:
            embed.set_footer(text="Link your account with /account link to add your subscription to this server")

        await ctx.followup.send(embed=embed, ephemeral=True)

    @account.command(description="Unlink your Discord from tavernrecap.com in this server")
    async def unlink(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)

        async with async_session() as db:
            result = await db.execute(
                select(UserLink).where(
                    UserLink.discord_user_id == ctx.author.id,
                    UserLink.guild_id == ctx.guild_id,
                )
            )
            link = result.scalar_one_or_none()

            if not link:
                await ctx.followup.send("No account linked in this server.", ephemeral=True)
                return

            await db.delete(link)
            await db.commit()

        await ctx.followup.send("Account unlinked from this server.", ephemeral=True)
        log.info(f"User {ctx.author} unlinked their account in guild {ctx.guild_id}")


def setup(bot: discord.Bot):
    bot.add_cog(AccountCog(bot))
