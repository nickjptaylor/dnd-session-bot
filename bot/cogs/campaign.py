import discord
from discord.ext import commands


class CampaignCog(commands.Cog):
    """Campaign management commands."""

    campaign = discord.SlashCommandGroup("campaign", "Manage your D&D campaigns")

    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @campaign.command(description="Create a new campaign for this server")
    async def create(self, ctx: discord.ApplicationContext, name: str, description: str = ""):
        await ctx.respond(f"Campaign **{name}** created! (DB persistence coming in Phase 2)")

    @campaign.command(description="List campaigns in this server")
    async def list(self, ctx: discord.ApplicationContext):
        await ctx.respond("No campaigns yet. Use `/campaign create` to start one.")


def setup(bot: discord.Bot):
    bot.add_cog(CampaignCog(bot))
