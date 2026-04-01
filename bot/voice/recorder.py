import io
import logging
import time

import discord

log = logging.getLogger(__name__)


class VoiceRecorder:
    """Manages voice recording for active sessions."""

    def __init__(self):
        self._active_connections: dict[int, discord.VoiceClient] = {}
        self._active_sinks: dict[int, discord.sinks.WaveSink] = {}
        self._start_times: dict[int, float] = {}

    def is_recording(self, guild_id: int) -> bool:
        return guild_id in self._active_connections

    def get_duration(self, guild_id: int) -> float:
        if guild_id in self._start_times:
            return time.time() - self._start_times[guild_id]
        return 0.0

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
        sink = discord.sinks.WaveSink()

        try:
            vc.start_recording(sink, self._on_recording_finished)
        except Exception:
            await vc.disconnect(force=True)
            raise

        self._active_connections[guild_id] = vc
        self._active_sinks[guild_id] = sink
        self._start_times[guild_id] = time.time()

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
        duration = self.get_duration(guild_id)
        self._start_times.pop(guild_id, None)

        try:
            # Grab raw audio data before stop_recording triggers cleanup/formatting
            # which can fail on the new Pycord voice internals
            audio_data: dict[int, io.BytesIO] = {}
            for user_id, audio in sink.audio_data.items():
                audio.file.seek(0)
                audio_data[user_id] = audio.file

            try:
                vc.stop_recording()
            except Exception as e:
                log.warning(f"Error during stop_recording cleanup (audio already captured): {e}")
        finally:
            await vc.disconnect(force=True)

        log.info(
            f"Stopped recording in guild {guild_id}. "
            f"Captured audio from {len(audio_data)} user(s), "
            f"duration: {duration:.1f}s"
        )
        return audio_data

    def _on_recording_finished(self, error: Exception | None) -> None:
        if error:
            log.error(f"Recording error: {error}")
        else:
            log.info("Recording finished")


# Singleton recorder instance
recorder = VoiceRecorder()
