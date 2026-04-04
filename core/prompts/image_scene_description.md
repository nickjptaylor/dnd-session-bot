You are creating an image generation prompt for a key moment from a Dungeons & Dragons session.

## Character Description
{% if character_description %}
{{ character_description }}
{% else %}
{{ character_name }}{% if character_race %}, a {{ character_race }}{% endif %}{% if character_class %} {{ character_class }}{% endif %}
{% endif %}

## Scene from the Session
{{ scene_description }}

## Instructions

{% if has_reference_image %}
IMPORTANT: A reference image of this character will be provided directly to the image generator. Your prompt should focus on the SCENE and ACTION rather than describing the character's appearance — the reference image handles that.

Write a detailed visual prompt for an AI image generator to create fantasy art of this scene. Your prompt should:

1. **Identify the character** — refer to them as "the character from the reference image" or "this character"
2. **Set the scene** — environment, lighting, atmosphere, time of day
3. **Capture the action** — what is the character doing in this moment
4. **Establish the mood** — dramatic, comedic, tense, triumphant, etc.
5. **Use art direction language** — reference fantasy art styles, composition, camera angle

Start with: "Place the character from the reference image into the following scene:"
{% else %}
Write a detailed visual prompt for an AI image generator (Flux) to create fantasy art of this scene. Your prompt should:

1. **Describe the character's appearance** — physical features, armor, weapons, clothing
2. **Set the scene** — environment, lighting, atmosphere, time of day
3. **Capture the action** — what is the character doing in this moment
4. **Establish the mood** — dramatic, comedic, tense, triumphant, etc.
5. **Use art direction language** — reference fantasy art styles, composition, camera angle
{% endif %}

Keep it to 2-3 sentences. Be specific and visual. Do NOT include any text, speech bubbles, or words in the scene.

Write the prompt now. No preamble — just the image prompt.