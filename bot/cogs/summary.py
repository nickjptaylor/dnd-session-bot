import discord
from discord.ext import commands


class SummaryCog(commands.Cog):
    """Session summary commands."""

    summary = discord.SlashCommandGroup("summary", "View session summaries")

    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @summary.command(description="View the last session summary")
    async def last(self, ctx: discord.ApplicationContext):
        await ctx.respond("No summaries yet. Record a session first with `/session start`.")

    @summary.command(description="View summary history for this campaign")
    async def history(self, ctx: discord.ApplicationContext):
        await ctx.respond("No session history yet.")


def setup(bot: discord.Bot):
    bot.add_cog(SummaryCog(bot))
