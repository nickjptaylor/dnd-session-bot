"""add dm_discord_id to campaigns

Revision ID: a1b2c3d4e5f6
Revises: d0445d51001d
Create Date: 2026-04-04 14:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'd0445d51001d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('campaigns', sa.Column('dm_discord_id', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column('campaigns', 'dm_discord_id')
