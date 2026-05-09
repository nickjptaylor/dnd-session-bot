import logging

import httpx
import discord
from discord.ext import commands
from sqlalchemy import select

from bot.config import settings
from core.db import async_session
from core.models.user_link import UserLink
from core.services.subscription import get_guild_subscription

log = logging.getLogger(__name__)


class AccountCog(commands.Cog):
    """Account linking and subscription commands."""

    account = discord.SlashCommandGroup("account", "Manage your Tavern Recap account")

    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @account.command(description="Link your tavernrecap.com account using a code from the website")
    async def link(
        self,
        ctx: discord.ApplicationContext,
        code: discord.Option(str, "The linking code from tavernrecap.com (e.g. TR-7X4K)"),
    ):
        await ctx.defer(ephemeral=True)

        # Call the bot API to verify the code and create the link
        try:
            api_url = "http://api:8000/api/link/verify"
            headers = {"Content-Type": "application/json"}
            if settings.bot_api_key:
                headers["x-bot-api-key"] = settings.bot_api_key

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    api_url,
                    json={
                        "code": code.upper().strip(),
                        "discord_user_id": ctx.author.id,
                        "guild_id": ctx.guild_id,
                    },
                    headers=headers,
                )

            if resp.status_code == 400:
                await ctx.followup.send(
                    "**Invalid or expired code.** Generate a new one at tavernrecap.com",
                    ephemeral=True,
                )
                return

            resp.raise_for_status()
            data = resp.json()

        except httpx.ConnectError:
            # API service might not be running — fall back to error
            log.error("Could not connect to bot API for code verification")
            await ctx.followup.send(
                "Could not verify code — API service unavailable. Try again in a moment.",
                ephemeral=True,
            )
            return
        except Exception:
            log.exception("Failed to verify linking code")
            await ctx.followup.send(
                "Something went wrong verifying your code. Try again or generate a new one at tavernrecap.com",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Account Linked!",
            description=f"Connected to **{data['email']}**",
            color=discord.Color.green(),
        )
        embed.add_field(name="Server Tier", value=data["tier_name"], inline=True)
        embed.set_footer(text="Your subscription now covers this entire server!")
        await ctx.followup.send(embed=embed, ephemeral=True)
        log.info(f"User {ctx.author} linked via code in guild {ctx.guild_id} ({data['tier_name']})")

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
            embed.set_footer(text="Link your account at tavernrecap.com to add your subscription to this server")

        await ctx.followup.send(embed=embed, ephemeral=True)

    @account.command(description="Unlink your account from this server")
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

            email = link.email
            guild_id = link.guild_id

            await db.delete(link)
            await db.commit()

        # Notify Lovable so the website updates in real time
        from core.services.lovable_callback import notify_unlink
        await notify_unlink(email=email, guild_id=guild_id)

        await ctx.followup.send("Account unlinked from this server.", ephemeral=True)
        log.info(f"User {ctx.author} unlinked their account in guild {ctx.guild_id}")


def setup(bot: discord.Bot):
    bot.add_cog(AccountCog(bot))
