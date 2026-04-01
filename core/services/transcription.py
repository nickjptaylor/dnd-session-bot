import asyncio
import json
import logging
from collections.abc import Callable

import websockets

log = logging.getLogger(__name__)


class DeepgramLiveTranscriber:
    """Streams audio to Deepgram's real-time WebSocket API and emits transcripts."""

    DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"

    def __init__(
        self,
        api_key: str,
        on_transcript: Callable[[str, bool], None] | None = None,
        language: str = "en",
        model: str = "nova-3",
    ):
        self.api_key = api_key
        self.on_transcript = on_transcript
        self.language = language
        self.model = model
        self._ws = None
        self._running = False
        self._full_transcript: list[str] = []

    @property
    def full_transcript(self) -> str:
        return " ".join(self._full_transcript)

    async def connect(self) -> None:
        params = (
            f"?model={self.model}"
            f"&language={self.language}"
            f"&encoding=linear16"
            f"&sample_rate=16000"
            f"&channels=1"
            f"&punctuate=true"
            f"&diarize=true"
            f"&smart_format=true"
            f"&interim_results=true"
        )
        url = self.DEEPGRAM_WS_URL + params
        headers = {"Authorization": f"Token {self.api_key}"}

        self._ws = await websockets.connect(url, additional_headers=headers)
        self._running = True
        log.info("Connected to Deepgram real-time API")

        # Start listening for responses
        asyncio.create_task(self._receive_loop())

    async def send_audio(self, audio_bytes: bytes) -> None:
        if self._ws and self._running:
            await self._ws.send(audio_bytes)

    async def close(self) -> None:
        self._running = False
        if self._ws:
            # Send close message to Deepgram
            await self._ws.send(json.dumps({"type": "CloseStream"}))
            await self._ws.close()
            self._ws = None
        log.info("Disconnected from Deepgram")

    async def _receive_loop(self) -> None:
        try:
            async for message in self._ws:
                data = json.loads(message)
                if data.get("type") == "Results":
                    channel = data.get("channel", {})
                    alternatives = channel.get("alternatives", [])
                    if not alternatives:
                        continue

                    transcript = alternatives[0].get("transcript", "").strip()
                    if not transcript:
                        continue

                    is_final = data.get("is_final", False)

                    if is_final:
                        self._full_transcript.append(transcript)

                    if self.on_transcript:
                        self.on_transcript(transcript, is_final)

                    log.debug(
                        f"{'[FINAL]' if is_final else '[interim]'} {transcript}"
                    )
        except websockets.exceptions.ConnectionClosed:
            log.info("Deepgram WebSocket connection closed")
        except Exception:
            log.exception("Error in Deepgram receive loop")
