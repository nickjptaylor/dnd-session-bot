"""add DM prep tables: story_threads, session_intros, plot_hooks

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-05-09 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6g7h8i9'
down_revision: Union[str, None] = 'c3d4e5f6g7h8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'story_threads',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('campaign_id', UUID(as_uuid=True), sa.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_session_id', UUID(as_uuid=True), sa.ForeignKey('sessions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('resolved_session_id', UUID(as_uuid=True), sa.ForeignKey('sessions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('thread_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_story_threads_campaign_id', 'story_threads', ['campaign_id'])
    op.create_index('ix_story_threads_status', 'story_threads', ['status'])

    op.create_table(
        'session_intros',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('campaign_id', UUID(as_uuid=True), sa.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False),
        sa.Column('generated_text', sa.Text, nullable=False),
        sa.Column('edited_text', sa.Text, nullable=True),
        sa.Column('source_summary_ids', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_session_intros_campaign_id', 'session_intros', ['campaign_id'])

    op.create_table(
        'plot_hooks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('campaign_id', UUID(as_uuid=True), sa.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_thread_id', UUID(as_uuid=True), sa.ForeignKey('story_threads.id', ondelete='SET NULL'), nullable=True),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('hook_type', sa.String(50), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='suggested'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_plot_hooks_campaign_id', 'plot_hooks', ['campaign_id'])
    op.create_index('ix_plot_hooks_status', 'plot_hooks', ['status'])


def downgrade() -> None:
    op.drop_table('plot_hooks')
    op.drop_table('session_intros')
    op.drop_table('story_threads')
