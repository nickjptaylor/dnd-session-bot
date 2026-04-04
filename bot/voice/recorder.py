import asyncio
import io
import logging
import time
import wave

import discord
from discord.opus import Decoder as OpusDecoder

log = logging.getLogger(__name__)


class VoiceRecorder:
    """Manages voice recording for active sessions."""

    def __init__(self):
        self._active_connections: dict[int, discord.VoiceClient] = {}
        self._active_sinks: dict[int, discord.sinks.WaveSink] = {}
        self._start_times: dict[int, float] = {}
        self._channel_ids: dict[int, int] = {}

    def is_recording(self, guild_id: int) -> bool:
        return guild_id in self._active_connections

    def get_channel_id(self, guild_id: int) -> int | None:
        return self._channel_ids.get(guild_id)

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

        # Wait for DAVE (Discord Audio/Video Encryption) handshake to complete.
        # Without this delay, the opus decoder hits "corrupted stream" errors
        # on the first few packets before encryption is fully negotiated.
        log.info("Waiting for DAVE handshake to settle...")
        await asyncio.sleep(3)

        sink = discord.sinks.WaveSink()

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                vc.start_recording(sink, self._on_recording_finished)
                break
            except Exception as e:
                if attempt < max_retries:
                    log.warning(f"Recording start attempt {attempt} failed ({e}), retrying in 2s...")
                    await asyncio.sleep(2)
                    sink = discord.sinks.WaveSink()  # fresh sink for retry
                else:
                    await vc.disconnect(force=True)
                    raise

        self._active_connections[guild_id] = vc
        self._active_sinks[guild_id] = sink
        self._start_times[guild_id] = time.time()
        self._channel_ids[guild_id] = voice_channel.id

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
        self._channel_ids.pop(guild_id, None)

        try:
            # Grab raw audio data before stop_recording triggers cleanup/formatting
            # which can fail on the new Pycord voice internals
            audio_data: dict[int, io.BytesIO] = {}
            for user, audio in sink.audio_data.items():
                user_id = user.id if hasattr(user, "id") else user
                audio.file.seek(0)
                pcm_data = audio.file.read()
                wav_buf = io.BytesIO()
                with wave.open(wav_buf, "wb") as wf:
                    wf.setnchannels(OpusDecoder.CHANNELS)
                    wf.setsampwidth(OpusDecoder.SAMPLE_SIZE // OpusDecoder.CHANNELS)
                    wf.setframerate(OpusDecoder.SAMPLING_RATE)
                    wf.writeframes(pcm_data)
                wav_buf.seek(0)
                audio_data[user_id] = wav_buf
                log.info(f"WAV buffer for user {user_id}: {len(pcm_data)} PCM bytes → {wav_buf.getbuffer().nbytes} WAV bytes")

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
