"""Add unique constraints to RBAC junction tables

Revision ID: 0015
Revises: 0014
Create Date: 2026-01-23 06:15:00.000000

CRITICAL FIX:
Add UNIQUE constraints to prevent:
- Duplicate role assignments (user_roles: user_id + role_id)
- Duplicate permission grants (role_permissions: role_id + permission_id)

This aligns the database schema with proper many-to-many junction table semantics
and prevents data integrity issues in the RBAC system.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str | None = '0015'
down_revision: Union[str, None] = '0014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply schema changes."""
    # Add UNIQUE constraint to user_roles (user_id, role_id)
    op.create_unique_constraint(
        "uq_user_roles_user_id_role_id",
        "user_roles",
        ["user_id", "role_id"]
    )
    
    # Add UNIQUE constraint to role_permissions (role_id, permission_id)
    op.create_unique_constraint(
        "uq_role_permissions_role_id_permission_id",
        "role_permissions",
        ["role_id", "permission_id"]
    )


def downgrade() -> None:
    """Revert schema changes."""
    # Drop UNIQUE constraint from role_permissions
    op.drop_constraint(
        "uq_role_permissions_role_id_permission_id",
        "role_permissions",
        type_="unique"
    )
    
    # Drop UNIQUE constraint from user_roles
    op.drop_constraint(
        "uq_user_roles_user_id_role_id",
        "user_roles",
        type_="unique"
    )
