import uuid

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models.base import Base, TimestampMixin, UUIDPrimaryKey


class SessionSummary(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "session_summaries"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), unique=True
    )
    narrative_summary: Mapped[str] = mapped_column(Text)
    dm_coaching_notes: Mapped[str | None] = mapped_column(Text)

    session: Mapped["Session"] = relationship(back_populates="summary")  # noqa: F821
    key_moments: Mapped[list["KeyMoment"]] = relationship(back_populates="summary")


class KeyMoment(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "key_moments"

    summary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("session_summaries.id", ondelete="CASCADE")
    )
    character_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id", ondelete="SET NULL")
    )
    discord_user_id: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column(Text)
    scene_prompt: Mapped[str | None] = mapped_column(Text)
    timestamp_in_session: Mapped[str | None] = mapped_column(String(20))

    summary: Mapped[SessionSummary] = relationship(back_populates="key_moments")
    art: Mapped["GeneratedArt | None"] = relationship(back_populates="key_moment")


class GeneratedArt(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "generated_art"

    key_moment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("key_moments.id", ondelete="CASCADE"), unique=True
    )
    s3_key: Mapped[str] = mapped_column(String(500))
    provider: Mapped[str] = mapped_column(String(50))  # "flux", "gpt_image"
    prompt_used: Mapped[str] = mapped_column(Text)

    key_moment: Mapped[KeyMoment] = relationship(back_populates="art")
