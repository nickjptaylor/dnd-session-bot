import io
import logging

import httpx

log = logging.getLogger(__name__)


class DeepgramBatchTranscriber:
    """Transcribes audio files via Deepgram's pre-recorded (batch) REST API."""

    API_URL = "https://api.deepgram.com/v1/listen"

    def __init__(self, api_key: str, model: str = "nova-3"):
        self.api_key = api_key
        self.model = model

    async def transcribe_audio(self, audio_bytes: bytes) -> dict:
        """Send audio to Deepgram pre-recorded API and return the raw response."""
        params = {
            "model": self.model,
            "language": "en",
            "punctuate": "true",
            "smart_format": "true",
            "utterances": "true",
        }
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "audio/wav",
        }

        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                self.API_URL,
                params=params,
                headers=headers,
                content=audio_bytes,
            )
            resp.raise_for_status()
            return resp.json()

    async def transcribe_users(
        self, user_audio: dict[int, io.BytesIO]
    ) -> list[tuple[int, list[dict]]]:
        """Transcribe multiple users' audio concurrently.

        Returns list of (discord_user_id, words) where each word dict has
        'start', 'end', 'punctuated_word' keys.
        """
        import asyncio

        async def _transcribe_one(user_id: int, audio_buf: io.BytesIO):
            audio_buf.seek(0)
            audio_bytes = audio_buf.read()

            if len(audio_bytes) < 100:
                log.warning(f"Skipping user {user_id}: audio too small ({len(audio_bytes)} bytes)")
                return user_id, []

            try:
                result = await self.transcribe_audio(audio_bytes)
            except httpx.HTTPStatusError as e:
                log.error(f"Deepgram API error for user {user_id}: {e.response.status_code} {e.response.text}")
                return user_id, []
            except Exception:
                log.exception(f"Failed to transcribe audio for user {user_id}")
                return user_id, []

            words = []
            channels = result.get("results", {}).get("channels", [])
            if channels:
                alternatives = channels[0].get("alternatives", [])
                if alternatives:
                    words = alternatives[0].get("words", [])

            log.info(f"Transcribed {len(words)} words for user {user_id}")
            return user_id, words

        tasks = [_transcribe_one(uid, buf) for uid, buf in user_audio.items()]
        results = await asyncio.gather(*tasks)
        return list(results)

    @staticmethod
    def merge_transcripts(
        user_words: list[tuple[int, list[dict]]],
        user_names: dict[int, str],
    ) -> str:
        """Merge per-user word lists into a single chronological, speaker-labelled transcript.

        Groups consecutive words by the same speaker into lines formatted as:
        [MM:SS] SpeakerName: words words words.
        """
        # Flatten all words with their speaker info
        all_words: list[tuple[float, int, str]] = []
        for user_id, words in user_words:
            for w in words:
                all_words.append((w["start"], user_id, w.get("punctuated_word", w.get("word", ""))))

        if not all_words:
            return ""

        all_words.sort(key=lambda x: x[0])

        # Group consecutive words by speaker into lines
        lines: list[str] = []
        current_speaker = None
        current_words: list[str] = []
        current_start = 0.0

        for start, user_id, word in all_words:
            if user_id != current_speaker:
                # Flush previous speaker's line
                if current_words:
                    name = user_names.get(current_speaker, f"User-{current_speaker}")
                    minutes = int(current_start // 60)
                    seconds = int(current_start % 60)
                    lines.append(f"[{minutes:02d}:{seconds:02d}] {name}: {' '.join(current_words)}")
                current_speaker = user_id
                current_words = [word]
                current_start = start
            else:
                current_words.append(word)

        # Flush last line
        if current_words:
            name = user_names.get(current_speaker, f"User-{current_speaker}")
            minutes = int(current_start // 60)
            seconds = int(current_start % 60)
            lines.append(f"[{minutes:02d}:{seconds:02d}] {name}: {' '.join(current_words)}")

        return "\n".join(lines)
