import discord


def session_started_embed(
    channel_name: str, started_by: str, participant_count: int
) -> discord.Embed:
    embed = discord.Embed(
        title="Session Recording Started",
        description=f"Recording in **{channel_name}**",
        color=discord.Color.green(),
    )
    embed.add_field(name="Started by", value=started_by, inline=True)
    embed.add_field(name="Participants", value=str(participant_count), inline=True)
    embed.set_footer(text="Use /session stop to end the recording")
    return embed


def session_stopped_embed(
    duration_seconds: float, user_count: int
) -> discord.Embed:
    minutes = int(duration_seconds // 60)
    seconds = int(duration_seconds % 60)

    embed = discord.Embed(
        title="Session Recording Stopped",
        description=f"Recorded **{minutes}m {seconds}s** of audio from **{user_count}** participant(s)",
        color=discord.Color.red(),
    )
    embed.set_footer(text="Processing pipeline will run automatically in future phases")
    return embed
