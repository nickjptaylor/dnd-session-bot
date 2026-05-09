import logging

import discord
from discord.ext import commands

log = logging.getLogger(__name__)


class HelpView(discord.ui.View):
    """Dropdown menu for navigating help topics."""

    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.select(
        placeholder="Choose a topic...",
        options=[
            discord.SelectOption(label="Quick Start", value="quickstart", emoji="🚀", description="Get up and running in 5 minutes"),
            discord.SelectOption(label="Session Recording", value="sessions", emoji="🎙️", description="Recording, transcribing, and summarising"),
            discord.SelectOption(label="Campaigns", value="campaigns", emoji="📜", description="Create and manage campaigns"),
            discord.SelectOption(label="Characters", value="characters", emoji="⚔️", description="Register characters and upload art"),
            discord.SelectOption(label="Homebrew", value="homebrew", emoji="🧪", description="Add custom lore, NPCs, and rules"),
            discord.SelectOption(label="Summaries & Art", value="summaries", emoji="🎨", description="View recaps and generated artwork"),
            discord.SelectOption(label="Account & Billing", value="account", emoji="💎", description="Link your account and manage subscription"),
            discord.SelectOption(label="DM Tools", value="dm", emoji="🧙", description="Coaching, session prep, and plot hooks"),
            discord.SelectOption(label="All Commands", value="commands", emoji="📋", description="Full command reference"),
        ],
    )
    async def select_topic(self, select: discord.ui.Select, interaction: discord.Interaction):
        topic = select.values[0]
        embed = HELP_TOPICS[topic]()
        await interaction.response.edit_message(embed=embed, view=self)


def _quickstart_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🚀 Quick Start Guide",
        description="Get Tavern Recap running for your group in 5 minutes.",
        color=discord.Color.gold(),
    )
    embed.add_field(
        name="Step 1 — Create a campaign",
        value="`/campaign create name:\"Curse of Strahd\"`\nGives your sessions a home. You can have multiple campaigns per server.",
        inline=False,
    )
    embed.add_field(
        name="Step 2 — Set the DM",
        value="`/campaign setdm dm:@YourDM`\nThe DM's speech is treated as narration and NPCs, not a player character.",
        inline=False,
    )
    embed.add_field(
        name="Step 3 — Register characters",
        value="`/character register name:\"Thorin\" race:\"Dwarf\" class:\"Fighter\" level:5`\nEach player registers their character so the bot knows who's who.",
        inline=False,
    )
    embed.add_field(
        name="Step 4 — Record a session",
        value="Join a voice channel, then:\n`/session start` — begins recording\n`/session stop` — ends recording and starts processing\n\nThe bot transcribes, summarises, extracts key moments, and generates art automatically.",
        inline=False,
    )
    embed.add_field(
        name="Step 5 — View your recap",
        value="The summary, key moments, and artwork are posted to the channel. You can also view everything on **tavernrecap.com**.",
        inline=False,
    )
    embed.set_footer(text="Use the dropdown above to explore more topics")
    return embed


def _sessions_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎙️ Session Recording",
        description="How recording, transcription, and summarisation work.",
        color=discord.Color.blue(),
    )
    embed.add_field(
        name="/session start",
        value="Join a voice channel first, then run this command. The bot joins and starts recording everyone in the channel. Each speaker is recorded separately for accurate transcription.",
        inline=False,
    )
    embed.add_field(
        name="/session stop",
        value="Stops the recording. The bot leaves the voice channel and begins processing in the background. You'll see progress updates in the channel.",
        inline=False,
    )
    embed.add_field(
        name="/session status",
        value="Check if a recording is currently active and how long it's been running.",
        inline=False,
    )
    embed.add_field(
        name="What happens after stop?",
        value="1. **Transcription** — Audio is sent to Deepgram for speech-to-text\n2. **Summary** — Claude AI writes a narrative recap\n3. **Key Moments** — The most dramatic moments are extracted per player\n4. **Artwork** — Each key moment gets a unique generated illustration\n5. **DM Coaching** — The DM gets private tips (if your tier includes it)\n\nThis usually takes 1-3 minutes depending on session length.",
        inline=False,
    )
    embed.set_footer(text="Sessions are auto-numbered and titled for easy browsing")
    return embed


def _campaigns_embed() -> discord.Embed:
    embed = discord.Embed(
        title="📜 Campaign Management",
        description="Campaigns organise your sessions, characters, and homebrew content.",
        color=discord.Color.dark_gold(),
    )
    embed.add_field(
        name="/campaign create",
        value="`/campaign create name:\"My Campaign\" description:\"A tale of...\"`\nCreates a new campaign and makes it the active one.",
        inline=False,
    )
    embed.add_field(
        name="/campaign list",
        value="Shows all campaigns in this server. The active one has a ✅.",
        inline=False,
    )
    embed.add_field(
        name="/campaign select",
        value="`/campaign select name:\"My Campaign\"`\nSwitches the active campaign. New sessions and commands will use this campaign.",
        inline=False,
    )
    embed.add_field(
        name="/campaign setdm",
        value="`/campaign setdm dm:@Username`\nSets who the DM is. Their speech is treated as narration/NPCs in transcripts, and they receive private coaching notes.",
        inline=False,
    )
    embed.add_field(
        name="/campaign setchannel",
        value="`/campaign setchannel channel:#recaps mode:thread`\nChoose where summaries are posted. Use `thread` mode to create a new thread per session.",
        inline=False,
    )
    embed.set_footer(text="Each server can have multiple campaigns — switch between them freely")
    return embed


def _characters_embed() -> discord.Embed:
    embed = discord.Embed(
        title="⚔️ Characters",
        description="Register your character so the bot can identify you in transcripts and generate personalised art.",
        color=discord.Color.purple(),
    )
    embed.add_field(
        name="/character register",
        value="`/character register name:\"Elara\" race:\"Half-Elf\" class:\"Ranger\" level:7`\nLinks your Discord account to your character for the active campaign.",
        inline=False,
    )
    embed.add_field(
        name="/character upload",
        value="`/character upload image:<attach a file>`\nUpload a reference image of your character. This is used when generating key moment artwork to keep your character looking consistent.",
        inline=False,
    )
    embed.add_field(
        name="/character list",
        value="Shows all characters registered in the active campaign.",
        inline=False,
    )
    embed.add_field(
        name="/character view",
        value="View your own character's details and reference image.",
        inline=False,
    )
    embed.set_footer(text="Tip: Upload a character portrait for the best generated art results")
    return embed


def _homebrew_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🧪 Homebrew Content",
        description="Add custom lore, NPCs, locations, rules, and items to your campaign. The bot uses this context to write better summaries and more accurate DM coaching.",
        color=discord.Color.dark_gold(),
    )
    embed.add_field(
        name="/campaign homebrew add",
        value=(
            "`/campaign homebrew add type:npc title:\"Bram Ironkettle\" content:\"Gruff dwarf blacksmith in Millhaven...\"`\n\n"
            "**Types:** `lore`, `npc`, `location`, `rule`, `item`"
        ),
        inline=False,
    )
    embed.add_field(
        name="/campaign homebrew list",
        value="Lists all homebrew entries. Optionally filter by type.",
        inline=False,
    )
    embed.add_field(
        name="/campaign homebrew view",
        value="View the full details of a specific entry.",
        inline=False,
    )
    embed.add_field(
        name="/campaign homebrew remove",
        value="Remove an entry you no longer need.",
        inline=False,
    )
    embed.add_field(
        name="Why add homebrew?",
        value="The more the bot knows about your world, the better it gets. Summaries will reference your NPCs by name, describe your locations accurately, and DM coaching will suggest ways to use your established lore.",
        inline=False,
    )
    return embed


def _summaries_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎨 Summaries & Artwork",
        description="After each session, the bot generates a narrative recap, key moment artwork, and more.",
        color=discord.Color.dark_purple(),
    )
    embed.add_field(
        name="/summary last",
        value="View the most recent session summary for the active campaign.",
        inline=False,
    )
    embed.add_field(
        name="/summary history",
        value="Browse past session summaries. Each session has a title, number, and full narrative recap.",
        inline=False,
    )
    embed.add_field(
        name="Key Moment Art",
        value="The bot picks the most dramatic moment for each player and generates a unique illustration. If you've uploaded a character reference image, the art will match your character's appearance.",
        inline=False,
    )
    embed.add_field(
        name="Web Dashboard",
        value="All sessions, summaries, and artwork are also available on **tavernrecap.com** — browse your campaign history, view art in full resolution, and share with your group.",
        inline=False,
    )
    return embed


def _account_embed() -> discord.Embed:
    embed = discord.Embed(
        title="💎 Account & Subscription",
        description="One person's subscription covers the entire server.",
        color=discord.Color.green(),
    )
    embed.add_field(
        name="/account link",
        value="`/account link code:TR-7X4K`\nLink your tavernrecap.com account using a one-time code from the website. This connects your subscription to this server.",
        inline=False,
    )
    embed.add_field(
        name="/account status",
        value="Check this server's current subscription tier and usage.",
        inline=False,
    )
    embed.add_field(
        name="/account unlink",
        value="Unlink your account from this server.",
        inline=False,
    )
    embed.add_field(
        name="Subscription Tiers",
        value=(
            "**Apprentice** (Free) — 2 sessions/month, no portraits\n"
            "**Tavern Regular** ($5/mo) — 4 sessions/month, 1 portrait/session\n"
            "**Adventurer** ($9/mo) — 8 sessions/month, 2 portraits, DM coaching\n"
            "**Guild Master** ($19/mo) — Unlimited everything"
        ),
        inline=False,
    )
    embed.set_footer(text="Subscribe at tavernrecap.com — one sub covers your whole server")
    return embed


def _dm_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🧙 DM Tools",
        description="Tools to help the Dungeon Master prep and improve.",
        color=discord.Color.teal(),
    )
    embed.add_field(
        name="DM Coaching Notes",
        value="After each session, the DM receives a private message with coaching tips — pacing, player engagement, storytelling, rules accuracy, and what went well. Available on Adventurer tier and above.",
        inline=False,
    )
    embed.add_field(
        name="Session Prep (tavernrecap.com)",
        value=(
            "On the website, DMs can:\n"
            "• **Generate a session intro** — A dramatic \"last time on...\" read-aloud recap\n"
            "• **Track story threads** — Unresolved quests, mysteries, and promises are automatically extracted from each session\n"
            "• **Get plot hook suggestions** — AI-generated hooks based on your active threads, characters, and lore\n"
            "• **One-click prep** — Generate intro, threads, and hooks all at once"
        ),
        inline=False,
    )
    embed.add_field(
        name="Setting Up as DM",
        value="Make sure to run `/campaign setdm dm:@You` so the bot knows you're the DM. This affects how your speech is transcribed and enables coaching notes.",
        inline=False,
    )
    return embed


def _commands_embed() -> discord.Embed:
    embed = discord.Embed(
        title="📋 All Commands",
        description="Complete command reference for Tavern Recap.",
        color=discord.Color.greyple(),
    )
    embed.add_field(
        name="📜 Campaign",
        value=(
            "`/campaign create` — Create a new campaign\n"
            "`/campaign list` — List all campaigns\n"
            "`/campaign select` — Switch active campaign\n"
            "`/campaign setdm` — Set the DM\n"
            "`/campaign setchannel` — Set summary output channel"
        ),
        inline=False,
    )
    embed.add_field(
        name="🧪 Homebrew",
        value=(
            "`/campaign homebrew add` — Add lore, NPCs, etc.\n"
            "`/campaign homebrew list` — List all entries\n"
            "`/campaign homebrew view` — View entry details\n"
            "`/campaign homebrew remove` — Remove an entry"
        ),
        inline=False,
    )
    embed.add_field(
        name="⚔️ Characters",
        value=(
            "`/character register` — Register your character\n"
            "`/character upload` — Upload reference art\n"
            "`/character list` — List party members\n"
            "`/character view` — View your character"
        ),
        inline=False,
    )
    embed.add_field(
        name="🎙️ Sessions",
        value=(
            "`/session start` — Start recording\n"
            "`/session stop` — Stop and process\n"
            "`/session status` — Check recording status"
        ),
        inline=False,
    )
    embed.add_field(
        name="🎨 Summaries",
        value=(
            "`/summary last` — View latest recap\n"
            "`/summary history` — Browse past sessions"
        ),
        inline=False,
    )
    embed.add_field(
        name="💎 Account",
        value=(
            "`/account link` — Link your website account\n"
            "`/account status` — Check subscription tier\n"
            "`/account unlink` — Unlink from this server"
        ),
        inline=False,
    )
    return embed


HELP_TOPICS = {
    "quickstart": _quickstart_embed,
    "sessions": _sessions_embed,
    "campaigns": _campaigns_embed,
    "characters": _characters_embed,
    "homebrew": _homebrew_embed,
    "summaries": _summaries_embed,
    "account": _account_embed,
    "dm": _dm_embed,
    "commands": _commands_embed,
}


class HelpCog(commands.Cog):
    """Interactive help system for Tavern Recap."""

    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @discord.slash_command(description="Learn how to use Tavern Recap")
    async def help(self, ctx: discord.ApplicationContext):
        embed = discord.Embed(
            title="Tavern Recap — Help",
            description=(
                "Your D&D sessions, transcribed, summarised, and illustrated.\n\n"
                "**Choose a topic below** to learn more, or start with 🚀 **Quick Start** to get set up."
            ),
            color=discord.Color.gold(),
        )
        embed.add_field(
            name="🚀 Quick Start",
            value="Get up and running in 5 minutes",
            inline=True,
        )
        embed.add_field(
            name="🎙️ Sessions",
            value="Recording and processing",
            inline=True,
        )
        embed.add_field(
            name="📜 Campaigns",
            value="Create and manage campaigns",
            inline=True,
        )
        embed.add_field(
            name="⚔️ Characters",
            value="Register and upload art",
            inline=True,
        )
        embed.add_field(
            name="🎨 Summaries",
            value="Recaps and generated art",
            inline=True,
        )
        embed.add_field(
            name="💎 Account",
            value="Subscription and linking",
            inline=True,
        )
        embed.set_footer(text="tavernrecap.com · Use the dropdown below to explore")

        view = HelpView()
        await ctx.respond(embed=embed, view=view, ephemeral=True)


def setup(bot: discord.Bot):
    bot.add_cog(HelpCog(bot))
