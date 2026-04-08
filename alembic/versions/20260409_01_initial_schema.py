"""Create initial Bot Society Markets schema.

Revision ID: 20260409_01
Revises: 
Create Date: 2026-04-09 15:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260409_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'bots',
        sa.Column('slug', sa.String(length=120), nullable=False, primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('archetype', sa.String(length=255), nullable=False),
        sa.Column('focus', sa.String(length=255), nullable=False),
        sa.Column('horizon_label', sa.String(length=255), nullable=False),
        sa.Column('thesis', sa.Text(), nullable=False),
        sa.Column('risk_style', sa.String(length=255), nullable=False),
        sa.Column('asset_universe', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.String(length=64), nullable=False),
    )
    op.create_table(
        'market_snapshots',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column('asset', sa.String(length=16), nullable=False),
        sa.Column('as_of', sa.String(length=64), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('change_24h', sa.Float(), nullable=False),
        sa.Column('volume_24h', sa.Float(), nullable=False),
        sa.Column('volatility', sa.Float(), nullable=False),
        sa.Column('trend_score', sa.Float(), nullable=False),
        sa.Column('signal_bias', sa.Float(), nullable=False),
        sa.Column('source', sa.String(length=120), nullable=False),
        sa.UniqueConstraint('asset', 'as_of', name='uq_market_snapshots_asset_as_of'),
    )
    op.create_table(
        'pipeline_runs',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column('cycle_type', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('started_at', sa.String(length=64), nullable=False),
        sa.Column('completed_at', sa.String(length=64)),
        sa.Column('ingested_signals', sa.Integer(), server_default='0', nullable=False),
        sa.Column('generated_predictions', sa.Integer(), server_default='0', nullable=False),
        sa.Column('scored_predictions', sa.Integer(), server_default='0', nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
    )
    op.create_table(
        'signals',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column('external_id', sa.String(length=255), nullable=False),
        sa.Column('asset', sa.String(length=16), nullable=False),
        sa.Column('source', sa.String(length=255), nullable=False),
        sa.Column('channel', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('sentiment', sa.Float(), nullable=False),
        sa.Column('relevance', sa.Float(), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('observed_at', sa.String(length=64), nullable=False),
        sa.Column('ingest_batch_id', sa.String(length=255), nullable=False),
        sa.UniqueConstraint('external_id'),
    )
    op.create_table(
        'users',
        sa.Column('slug', sa.String(length=120), nullable=False, primary_key=True),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('tier', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.Column('password_hash', sa.String(length=512)),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.UniqueConstraint('email'),
    )
    op.create_table(
        'alert_rules',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column('user_slug', sa.String(length=120), nullable=False),
        sa.Column('bot_slug', sa.String(length=120)),
        sa.Column('asset', sa.String(length=16)),
        sa.Column('min_confidence', sa.Float(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['bot_slug'], ['bots.slug'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_slug'], ['users.slug'], ondelete='CASCADE'),
    )
    op.create_table(
        'notification_channels',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column('user_slug', sa.String(length=120), nullable=False),
        sa.Column('channel_type', sa.String(length=32), nullable=False),
        sa.Column('target', sa.Text(), nullable=False),
        sa.Column('secret', sa.String(length=255)),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.Column('last_delivered_at', sa.String(length=64)),
        sa.Column('last_error', sa.Text()),
        sa.ForeignKeyConstraint(['user_slug'], ['users.slug'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_slug', 'channel_type', 'target', name='uq_notification_channels_user_type_target'),
    )
    op.create_table(
        'predictions',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column('bot_slug', sa.String(length=120), nullable=False),
        sa.Column('asset', sa.String(length=16), nullable=False),
        sa.Column('direction', sa.String(length=16), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('horizon_days', sa.Integer(), nullable=False),
        sa.Column('horizon_label', sa.String(length=120), nullable=False),
        sa.Column('thesis', sa.Text(), nullable=False),
        sa.Column('trigger_conditions', sa.Text(), nullable=False),
        sa.Column('invalidation', sa.Text(), nullable=False),
        sa.Column('source_signal_ids', sa.Text(), nullable=False),
        sa.Column('published_at', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('start_price', sa.Float()),
        sa.Column('end_price', sa.Float()),
        sa.Column('market_return', sa.Float()),
        sa.Column('strategy_return', sa.Float()),
        sa.Column('max_adverse_excursion', sa.Float()),
        sa.Column('score', sa.Float()),
        sa.Column('calibration_score', sa.Float()),
        sa.Column('directional_success', sa.Boolean()),
        sa.Column('scoring_version', sa.String(length=32)),
        sa.ForeignKeyConstraint(['bot_slug'], ['bots.slug']),
    )
    op.create_table(
        'user_follows',
        sa.Column('user_slug', sa.String(length=120), nullable=False),
        sa.Column('bot_slug', sa.String(length=120), nullable=False),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['bot_slug'], ['bots.slug'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_slug'], ['users.slug'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_slug', 'bot_slug', name='uq_user_follows_user_bot'),
    )
    op.create_table(
        'user_sessions',
        sa.Column('token_hash', sa.String(length=128), nullable=False, primary_key=True),
        sa.Column('user_slug', sa.String(length=120), nullable=False),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.String(length=64), nullable=False),
        sa.Column('last_seen_at', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['user_slug'], ['users.slug'], ondelete='CASCADE'),
    )
    op.create_table(
        'watchlist_items',
        sa.Column('user_slug', sa.String(length=120), nullable=False),
        sa.Column('asset', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.UniqueConstraint('user_slug', 'asset', name='uq_watchlist_items_user_asset'),
        sa.ForeignKeyConstraint(['user_slug'], ['users.slug'], ondelete='CASCADE'),
    )
    op.create_table(
        'alert_delivery_events',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column('user_slug', sa.String(length=120), nullable=False),
        sa.Column('rule_id', sa.Integer()),
        sa.Column('notification_channel_id', sa.Integer()),
        sa.Column('prediction_id', sa.Integer(), nullable=False),
        sa.Column('bot_slug', sa.String(length=120), nullable=False),
        sa.Column('asset', sa.String(length=16), nullable=False),
        sa.Column('direction', sa.String(length=16), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('channel', sa.String(length=32), nullable=False),
        sa.Column('channel_target', sa.Text(), nullable=False),
        sa.Column('delivery_status', sa.String(length=32), nullable=False),
        sa.Column('attempt_count', sa.Integer(), server_default='1', nullable=False),
        sa.Column('last_attempt_at', sa.String(length=64)),
        sa.Column('next_attempt_at', sa.String(length=64)),
        sa.Column('error_detail', sa.Text()),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.Column('read_at', sa.String(length=64)),
        sa.UniqueConstraint('user_slug', 'rule_id', 'prediction_id', 'channel', name='uq_alert_delivery_event_scope'),
        sa.ForeignKeyConstraint(['notification_channel_id'], ['notification_channels.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['rule_id'], ['alert_rules.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_slug'], ['users.slug'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['bot_slug'], ['bots.slug'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['prediction_id'], ['predictions.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_market_snapshots_asset_as_of', 'market_snapshots', ['asset', 'as_of'], unique=False)
    op.create_index('idx_pipeline_runs_started_at', 'pipeline_runs', ['started_at'], unique=False)
    op.create_index('idx_signals_observed_at', 'signals', ['observed_at'], unique=False)
    op.create_index('idx_alert_rules_user', 'alert_rules', ['user_slug', 'created_at'], unique=False)
    op.create_index('idx_notification_channels_user', 'notification_channels', ['user_slug', 'created_at'], unique=False)
    op.create_index('idx_predictions_published_at', 'predictions', ['published_at'], unique=False)
    op.create_index('idx_predictions_status', 'predictions', ['status', 'published_at'], unique=False)
    op.create_index('idx_alert_delivery_events_user', 'alert_delivery_events', ['user_slug', 'created_at'], unique=False)
    op.create_index('idx_alert_delivery_events_unread', 'alert_delivery_events', ['user_slug', 'read_at', 'created_at'], unique=False)
    op.create_index('idx_alert_delivery_events_retry', 'alert_delivery_events', ['delivery_status', 'next_attempt_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_alert_delivery_events_user', table_name='alert_delivery_events')
    op.drop_index('idx_alert_delivery_events_unread', table_name='alert_delivery_events')
    op.drop_index('idx_alert_delivery_events_retry', table_name='alert_delivery_events')
    op.drop_index('idx_predictions_published_at', table_name='predictions')
    op.drop_index('idx_predictions_status', table_name='predictions')
    op.drop_index('idx_notification_channels_user', table_name='notification_channels')
    op.drop_index('idx_alert_rules_user', table_name='alert_rules')
    op.drop_index('idx_signals_observed_at', table_name='signals')
    op.drop_index('idx_pipeline_runs_started_at', table_name='pipeline_runs')
    op.drop_index('idx_market_snapshots_asset_as_of', table_name='market_snapshots')
    op.drop_table('alert_delivery_events')
    op.drop_table('watchlist_items')
    op.drop_table('user_sessions')
    op.drop_table('user_follows')
    op.drop_table('predictions')
    op.drop_table('notification_channels')
    op.drop_table('alert_rules')
    op.drop_table('users')
    op.drop_table('signals')
    op.drop_table('pipeline_runs')
    op.drop_table('market_snapshots')
    op.drop_table('bots')
