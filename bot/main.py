import logging
import sys

import discord

from bot.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)
log = logging.getLogger("dnd-bot")

# Suppress noisy voice/sink logs that flood the console during recording
logging.getLogger("discord.voice.receive.reader").setLevel(logging.CRITICAL)
logging.getLogger("discord.voice.receive.router").setLevel(logging.WARNING)
logging.getLogger("discord.sinks").setLevel(logging.CRITICAL)

# Parse debug guild IDs from comma-separated env var (instant command registration)
_debug_guilds = (
    [int(gid.strip()) for gid in settings.debug_guild_ids.split(",") if gid.strip()]
    if settings.debug_guild_ids
    else None
)

bot = discord.Bot(
    intents=discord.Intents.default() | discord.Intents.voice_states,
    debug_guilds=_debug_guilds or discord.utils.MISSING,
)


@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    log.info(f"Connected to {len(bot.guilds)} guild(s)")
    for guild in bot.guilds:
        log.info(f"  Guild: {guild.name} (ID: {guild.id})")
    await bot.sync_commands()
    log.info("Commands synced")


def run():
    bot.load_extension("bot.cogs.session")
    bot.load_extension("bot.cogs.campaign")
    bot.load_extension("bot.cogs.character")
    bot.load_extension("bot.cogs.summary")
    bot.load_extension("bot.cogs.account")
    bot.run(settings.discord_bot_token)


if __name__ == "__main__":
    run()
