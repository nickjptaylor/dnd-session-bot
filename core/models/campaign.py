import uuid

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models.base import Base, TimestampMixin, UUIDPrimaryKey


class Campaign(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "campaigns"

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    created_by_discord_id: Mapped[int] = mapped_column(BigInteger)

    sourcebooks: Mapped[list["Sourcebook"]] = relationship(back_populates="campaign")
    homebrew_contents: Mapped[list["HomebrewContent"]] = relationship(back_populates="campaign")
    characters: Mapped[list["Character"]] = relationship(back_populates="campaign")  # noqa: F821
    sessions: Mapped[list["Session"]] = relationship(back_populates="campaign")  # noqa: F821


class Sourcebook(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "sourcebooks"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(200))
    abbreviation: Mapped[str] = mapped_column(String(20))

    campaign: Mapped[Campaign] = relationship(back_populates="sourcebooks")


class HomebrewContent(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "homebrew_contents"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(50))  # "lore", "rule", "item", etc.

    campaign: Mapped[Campaign] = relationship(back_populates="homebrew_contents")
