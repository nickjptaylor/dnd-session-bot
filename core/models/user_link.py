from sqlalchemy import BigInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.models.base import Base, TimestampMixin, UUIDPrimaryKey


class UserLink(Base, UUIDPrimaryKey, TimestampMixin):
    """Links a Discord user to their tavernrecap.com account (by email), scoped to a guild.

    A user can link their account in multiple guilds — their subscription
    covers any guild where they've linked.
    """
    __tablename__ = "user_links"
    __table_args__ = (
        UniqueConstraint("discord_user_id", "guild_id", name="uq_user_guild"),
    )

    discord_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)

    # Cached subscription info (refreshed on each session start)
    stripe_product_id: Mapped[str | None] = mapped_column(String(100))
    subscription_tier: Mapped[str] = mapped_column(String(50), default="free")
