import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models.base import Base, TimestampMixin, UUIDPrimaryKey


class StoryThread(Base, UUIDPrimaryKey, TimestampMixin):
    """An unresolved narrative thread tracked across sessions."""

    __tablename__ = "story_threads"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE")
    )
    source_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="SET NULL")
    )
    resolved_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    thread_type: Mapped[str] = mapped_column(String(50))
    # "quest", "mystery", "promise", "escaped_villain", "relationship", "other"
    status: Mapped[str] = mapped_column(String(20), default="active")
    # "active", "resolved", "dismissed"

    campaign: Mapped["Campaign"] = relationship(back_populates="story_threads")  # noqa: F821
    source_session: Mapped["Session | None"] = relationship(  # noqa: F821
        foreign_keys=[source_session_id]
    )
    resolved_session: Mapped["Session | None"] = relationship(  # noqa: F821
        foreign_keys=[resolved_session_id]
    )


class SessionIntro(Base, UUIDPrimaryKey, TimestampMixin):
    """A generated 'last time on...' read-aloud intro for the DM."""

    __tablename__ = "session_intros"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE")
    )
    generated_text: Mapped[str] = mapped_column(Text)
    edited_text: Mapped[str | None] = mapped_column(Text)
    source_summary_ids: Mapped[str] = mapped_column(Text)
    # JSON array of session IDs used as context

    campaign: Mapped["Campaign"] = relationship()  # noqa: F821


class PlotHook(Base, UUIDPrimaryKey, TimestampMixin):
    """A Claude-suggested plot hook the DM can pin, dismiss, or use."""

    __tablename__ = "plot_hooks"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE")
    )
    source_thread_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("story_threads.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    hook_type: Mapped[str | None] = mapped_column(String(50))
    # "combat", "roleplay", "exploration", "social", "mystery"
    status: Mapped[str] = mapped_column(String(20), default="suggested")
    # "suggested", "pinned", "dismissed", "used"

    campaign: Mapped["Campaign"] = relationship()  # noqa: F821
    source_thread: Mapped["StoryThread | None"] = relationship()
