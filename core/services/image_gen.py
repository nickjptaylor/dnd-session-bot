import asyncio
import base64
import logging
from pathlib import Path

import anthropic
import httpx
from jinja2 import Template

log = logging.getLogger(__name__)

SCENE_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "image_scene_description.md"


class FluxImageGenerator:
    """Generates fantasy art using BFL's Flux Kontext Pro API with character reference support."""

    BFL_API_URL = "https://api.bfl.ai/v1/flux-kontext-pro"
    BFL_RESULT_URL = "https://api.bfl.ai/v1/get_result"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate_image(
        self,
        prompt: str,
        reference_image: bytes | None = None,
        width: int = 1024,
        height: int = 1024,
    ) -> bytes:
        """Generate an image from a prompt and optional reference image.

        Uses BFL's Flux Kontext Pro with async polling:
        1. Submit generation request (with reference image if provided)
        2. Poll for result
        3. Download image from result URL
        """
        headers = {
            "X-Key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "prompt": prompt,
            "aspect_ratio": "1:1",
            "safety_tolerance": 2,
            "output_format": "jpeg",
        }

        # Pass reference image as base64 for character consistency
        if reference_image:
            b64_image = base64.b64encode(reference_image).decode("utf-8")
            payload["input_image"] = b64_image
            log.info(f"Including reference image ({len(reference_image)} bytes) for character consistency")

        async with httpx.AsyncClient(timeout=180) as client:
            # Submit the request
            resp = await client.post(
                self.BFL_API_URL,
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            result = resp.json()
            task_id = result["id"]
            polling_url = result.get("polling_url", f"{self.BFL_RESULT_URL}?id={task_id}")
            log.info(f"Flux Kontext generation submitted (task_id={task_id})")

            # Poll for result
            image_url = await self._poll_for_result(client, polling_url, headers)

            # Download the image
            img_resp = await client.get(image_url)
            img_resp.raise_for_status()
            log.info(f"Downloaded generated image ({len(img_resp.content)} bytes)")
            return img_resp.content

    async def _poll_for_result(
        self,
        client: httpx.AsyncClient,
        polling_url: str,
        headers: dict,
        max_wait: int = 120,
        interval: float = 1.0,
    ) -> str:
        """Poll the BFL result endpoint until the image is ready."""
        elapsed = 0.0
        while elapsed < max_wait:
            resp = await client.get(
                polling_url,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status")

            if status == "Ready":
                return data["result"]["sample"]
            elif status in ("Error", "Failed"):
                raise RuntimeError(f"Flux generation failed: {data}")

            await asyncio.sleep(interval)
            elapsed += interval

        raise TimeoutError(f"Flux generation timed out after {max_wait}s (polling_url={polling_url})")


class ScenePromptGenerator:
    """Uses Claude to create detailed image prompts from key moment descriptions."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self._template = Template(SCENE_PROMPT_PATH.read_text())

    async def generate_prompt(
        self,
        scene_description: str,
        character_name: str = "",
        character_race: str | None = None,
        character_class: str | None = None,
        character_description: str | None = None,
        has_reference_image: bool = False,
        homebrew_context: str | None = None,
    ) -> str:
        """Generate a detailed image prompt from a scene description and character info."""
        prompt = self._template.render(
            scene_description=scene_description,
            character_name=character_name,
            character_race=character_race,
            character_class=character_class,
            character_description=character_description,
            has_reference_image=has_reference_image,
            homebrew_context=homebrew_context,
        )

        message = await self.client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        image_prompt = message.content[0].text
        log.info(f"Generated image prompt for {character_name}: {image_prompt[:100]}...")
        return image_prompt
