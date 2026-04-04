import logging

import discord

from bot.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("dnd-bot")

# Suppress noisy voice receive logs that flood the console during recording
logging.getLogger("discord.voice.receive.reader").setLevel(logging.WARNING)
logging.getLogger("discord.voice.receive.router").setLevel(logging.WARNING)

bot = discord.Bot(
    intents=discord.Intents.default() | discord.Intents.voice_states,
    debug_guilds=[1203373115778924554],
)


@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    log.info(f"Connected to {len(bot.guilds)} guild(s)")
    for guild in bot.guilds:
        log.info(f"  Guild: {guild.name} (ID: {guild.id})")
    await bot.sync_commands(force=True)
    log.info("Commands synced")


def run():
    bot.load_extension("bot.cogs.session")
    bot.load_extension("bot.cogs.campaign")
    bot.load_extension("bot.cogs.character")
    bot.load_extension("bot.cogs.summary")
    bot.run(settings.discord_bot_token)


if __name__ == "__main__":
    run()
