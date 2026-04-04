You are analyzing a Dungeons & Dragons session transcript to identify the most memorable moments for each player.

## Characters in This Session
{% for char in characters %}
- **{{ char.name }}** (played by {{ char.player_name }}, Discord ID: {{ char.discord_user_id }}){% if char.race %}, {{ char.race }}{% endif %}{% if char.character_class %} {{ char.character_class }}{% endif %}
{% endfor %}
{% if not characters %}
(No character profiles registered — use speaker names from the transcript as both character and player names)
{% endif %}
{% if homebrew_context %}

## Campaign World
Use these homebrew details to make scene_prompt descriptions more accurate — reference actual locations, NPC appearances, and items from the campaign world.

{{ homebrew_context }}
{% endif %}

## Session Transcript
{{ transcript }}

## Instructions

Identify 1 standout moment per player/speaker in this session. These should be the moments players would want to remember — epic combat moves, hilarious roleplay, clutch saves, dramatic story beats, or meaningful character interactions.

For each moment, provide:
- **player_name**: The speaker/player name as it appears in the transcript
- **discord_user_id**: The Discord user ID if known, otherwise null
- **description**: A 1-2 sentence description of what happened (written vividly, in past tense)
- **scene_prompt**: A visual description of the scene suitable for generating fantasy art (describe the character, action, setting, lighting, mood — NO text or speech bubbles)
- **timestamp**: The approximate timestamp from the transcript (e.g. "05:23")

Respond with valid JSON only — an array of moment objects. No preamble or commentary.

```json
[
  {
    "player_name": "...",
    "discord_user_id": null,
    "description": "...",
    "scene_prompt": "...",
    "timestamp": "..."
  }
]
```