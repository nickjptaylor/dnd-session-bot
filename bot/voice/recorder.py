import io
import logging
import time
from collections import defaultdict

import discord

log = logging.getLogger(__name__)


class SessionSink(discord.sinks.WaveSink):
    """Extended WaveSink that tracks per-user audio data for a session."""

    def __init__(self):
        super().__init__()
        self.start_time: float = time.time()
        self.user_audio: dict[int, list[bytes]] = defaultdict(list)

    @property
    def duration_seconds(self) -> float:
        return time.time() - self.start_time


class VoiceRecorder:
    """Manages voice recording for active sessions."""

    def __init__(self):
        self._active_connections: dict[int, discord.VoiceClient] = {}  # guild_id -> vc
        self._active_sinks: dict[int, SessionSink] = {}  # guild_id -> sink

    def is_recording(self, guild_id: int) -> bool:
        return guild_id in self._active_connections

    async def start_recording(
        self, voice_channel: discord.VoiceChannel
    ) -> discord.VoiceClient:
        guild_id = voice_channel.guild.id

        if self.is_recording(guild_id):
            raise RuntimeError("Already recording in this server")

        # Clean up any stale voice connection from a previous failed attempt
        existing_vc = voice_channel.guild.voice_client
        if existing_vc:
            log.warning(f"Found stale voice connection in guild {guild_id}, disconnecting")
            await existing_vc.disconnect(force=True)

        vc = await voice_channel.connect()
        sink = SessionSink()

        try:
            vc.start_recording(sink, self._on_recording_finished, voice_channel)
        except Exception:
            await vc.disconnect(force=True)
            raise

        self._active_connections[guild_id] = vc
        self._active_sinks[guild_id] = sink

        log.info(f"Started recording in {voice_channel.name} (guild {guild_id})")
        return vc

    async def stop_recording(self, guild_id: int) -> dict[int, io.BytesIO]:
        """Stop recording and return per-user audio buffers.

        Returns a dict mapping Discord user IDs to their WAV audio data.
        """
        if not self.is_recording(guild_id):
            raise RuntimeError("Not recording in this server")

        vc = self._active_connections.pop(guild_id)
        sink = self._active_sinks.pop(guild_id)

        try:
            vc.stop_recording()

            audio_data: dict[int, io.BytesIO] = {}
            for user_id, audio in sink.audio_data.items():
                audio_data[user_id] = audio.file
        finally:
            await vc.disconnect(force=True)

        log.info(
            f"Stopped recording in guild {guild_id}. "
            f"Captured audio from {len(audio_data)} user(s), "
            f"duration: {sink.duration_seconds:.1f}s"
        )
        return audio_data

    def _on_recording_finished(self, sink: discord.sinks.Sink, channel: discord.VoiceChannel):
        log.info(f"Recording finished callback for {channel.name}")


# Singleton recorder instance
recorder = VoiceRecorder()
