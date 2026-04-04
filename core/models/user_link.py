from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from core.models.base import Base, TimestampMixin, UUIDPrimaryKey


class UserLink(Base, UUIDPrimaryKey, TimestampMixin):
    """Links a Discord user to their tavernrecap.com account (by email)."""
    __tablename__ = "user_links"

    discord_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)

    # Cached subscription info (refreshed on each session start)
    stripe_product_id: Mapped[str | None] = mapped_column(String(100))
    subscription_tier: Mapped[str] = mapped_column(String(50), default="free")
