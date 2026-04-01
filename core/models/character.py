import uuid

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models.base import Base, TimestampMixin, UUIDPrimaryKey


class Character(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "characters"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE")
    )
    discord_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(200))
    race: Mapped[str | None] = mapped_column(String(100))
    character_class: Mapped[str | None] = mapped_column(String(100))
    level: Mapped[int | None]
    description: Mapped[str | None] = mapped_column(Text)

    campaign: Mapped["Campaign"] = relationship(back_populates="characters")  # noqa: F821
    references: Mapped[list["CharacterReference"]] = relationship(back_populates="character")


class CharacterReference(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "character_references"

    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE")
    )
    s3_key: Mapped[str] = mapped_column(String(500))
    filename: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(100))

    character: Mapped[Character] = relationship(back_populates="references")
