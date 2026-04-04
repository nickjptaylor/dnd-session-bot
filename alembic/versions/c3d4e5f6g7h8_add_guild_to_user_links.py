"""add guild_id to user_links for per-server subscriptions

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-04-04 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add guild_id column (default 0 for existing rows)
    op.add_column('user_links', sa.Column('guild_id', sa.BigInteger(), nullable=False, server_default='0'))

    # Drop old unique index on discord_user_id alone (it was an index, not a constraint)
    op.drop_index('ix_user_links_discord_user_id', 'user_links')

    # Add new composite unique constraint (user + guild)
    op.create_unique_constraint('uq_user_guild', 'user_links', ['discord_user_id', 'guild_id'])

    # Add indexes for lookups
    op.create_index('ix_user_links_discord_user_id', 'user_links', ['discord_user_id'])
    op.create_index('ix_user_links_guild_id', 'user_links', ['guild_id'])


def downgrade() -> None:
    op.drop_index('ix_user_links_guild_id', 'user_links')
    op.drop_index('ix_user_links_discord_user_id', 'user_links')
    op.drop_constraint('uq_user_guild', 'user_links', type_='unique')
    op.create_index('ix_user_links_discord_user_id', 'user_links', ['discord_user_id'], unique=True)
    op.drop_column('user_links', 'guild_id')
