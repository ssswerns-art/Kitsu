"""Add audit_logs actor_type check constraint

Revision ID: 0014
Revises: 0013
Create Date: 2026-01-23 05:18:00.000000

SECURITY FIX:
Add database-level CHECK constraint to enforce that actor_type can only be
'user', 'system', or 'anonymous'. This aligns the database schema with the
model definition and prevents invalid actor_type values from being inserted
via raw SQL, addressing SECURITY-01 contract requirements.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str | None = '0014'
down_revision: Union[str, None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply schema changes."""
    op.create_check_constraint(
        "valid_actor_type",
        "audit_logs",
        "actor_type IN ('user', 'system', 'anonymous')"
    )


def downgrade() -> None:
    """Revert schema changes."""
    op.drop_constraint("valid_actor_type", "audit_logs", type_="check")
