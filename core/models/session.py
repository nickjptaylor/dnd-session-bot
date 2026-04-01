import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models.base import Base, TimestampMixin, UUIDPrimaryKey


class Session(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "sessions"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE")
    )
    session_number: Mapped[int | None]
    title: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="recording")  # recording, processing, complete, failed
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    voice_channel_id: Mapped[int] = mapped_column(BigInteger)
    started_by_discord_id: Mapped[int] = mapped_column(BigInteger)

    campaign: Mapped["Campaign"] = relationship(back_populates="sessions")  # noqa: F821
    recordings: Mapped[list["SessionRecording"]] = relationship(back_populates="session")
    transcripts: Mapped[list["Transcript"]] = relationship(back_populates="session")
    summary: Mapped["SessionSummary | None"] = relationship(back_populates="session")  # noqa: F821


class SessionRecording(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "session_recordings"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE")
    )
    discord_user_id: Mapped[int] = mapped_column(BigInteger)
    s3_key: Mapped[str] = mapped_column(String(500))
    duration_seconds: Mapped[float | None]
    format: Mapped[str] = mapped_column(String(20), default="pcm")

    session: Mapped[Session] = relationship(back_populates="recordings")


class Transcript(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "transcripts"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE")
    )
    provider: Mapped[str] = mapped_column(String(50))  # "deepgram" or "assemblyai"
    content: Mapped[str] = mapped_column(Text)
    is_final: Mapped[bool] = mapped_column(default=False)

    session: Mapped[Session] = relationship(back_populates="transcripts")
