import discord
from discord.ext import commands


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
    ):
        await ctx.respond(
            f"Character **{name}** registered! (DB persistence coming in Phase 2)"
        )

    @character.command(description="List characters in the current campaign")
    async def list(self, ctx: discord.ApplicationContext):
        await ctx.respond("No characters yet. Use `/character create` to add one.")


def setup(bot: discord.Bot):
    bot.add_cog(CharacterCog(bot))
