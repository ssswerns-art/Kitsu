"""Add admin core tables and extend anime episode with ownership locks"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str | None = '0013'
down_revision: Union[str, None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply schema changes."""
    # Create roles table
    op.create_table(
        'roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_system', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_roles')),
        sa.UniqueConstraint('name', name=op.f('uq_roles_name'))
    )
    op.create_index('ix_roles_name', 'roles', ['name'], unique=False)
    
    # Create permissions table
    op.create_table(
        'permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('resource', sa.String(length=100), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('is_system', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_permissions')),
        sa.UniqueConstraint('name', name=op.f('uq_permissions_name'))
    )
    op.create_index('ix_permissions_name', 'permissions', ['name'], unique=False)
    op.create_index('ix_permissions_resource', 'permissions', ['resource'], unique=False)
    
    # Create role_permissions table
    op.create_table(
        'role_permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('permission_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name=op.f('fk_role_permissions_role_id_roles'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], name=op.f('fk_role_permissions_permission_id_permissions'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_role_permissions'))
    )
    op.create_index('ix_role_permissions_role_id', 'role_permissions', ['role_id'], unique=False)
    op.create_index('ix_role_permissions_permission_id', 'role_permissions', ['permission_id'], unique=False)
    
    # Create user_roles table
    op.create_table(
        'user_roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('granted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('granted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_roles_user_id_users'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name=op.f('fk_user_roles_role_id_roles'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['granted_by'], ['users.id'], name=op.f('fk_user_roles_granted_by_users'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_user_roles'))
    )
    op.create_index('ix_user_roles_user_id', 'user_roles', ['user_id'], unique=False)
    op.create_index('ix_user_roles_role_id', 'user_roles', ['role_id'], unique=False)
    
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('actor_type', sa.String(length=50), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('entity_type', sa.String(length=100), nullable=False),
        sa.Column('entity_id', sa.String(length=255), nullable=False),
        sa.Column('before', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('after', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_audit_logs_actor_id_users'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_logs'))
    )
    op.create_index('ix_audit_logs_actor_id', 'audit_logs', ['actor_id'], unique=False)
    op.create_index('ix_audit_logs_actor_type', 'audit_logs', ['actor_type'], unique=False)
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'], unique=False)
    op.create_index('ix_audit_logs_entity_type', 'audit_logs', ['entity_type'], unique=False)
    op.create_index('ix_audit_logs_entity_id', 'audit_logs', ['entity_id'], unique=False)
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'], unique=False)
    
    # Extend anime table with ownership, locks, and soft delete
    op.add_column('anime', sa.Column('state', sa.String(length=50), server_default='draft', nullable=False))
    op.add_column('anime', sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('anime', sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('anime', sa.Column('source', sa.String(length=50), server_default='manual', nullable=False))
    op.add_column('anime', sa.Column('is_locked', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('anime', sa.Column('locked_fields', postgresql.ARRAY(sa.String(length=100)), nullable=True))
    op.add_column('anime', sa.Column('locked_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('anime', sa.Column('locked_reason', sa.Text(), nullable=True))
    op.add_column('anime', sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('anime', sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('anime', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('anime', sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('anime', sa.Column('delete_reason', sa.Text(), nullable=True))
    op.add_column('anime', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    
    op.create_index('ix_anime_state', 'anime', ['state'], unique=False)
    op.create_index('ix_anime_is_deleted', 'anime', ['is_deleted'], unique=False)
    op.create_foreign_key(op.f('fk_anime_created_by_users'), 'anime', 'users', ['created_by'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(op.f('fk_anime_updated_by_users'), 'anime', 'users', ['updated_by'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(op.f('fk_anime_locked_by_users'), 'anime', 'users', ['locked_by'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(op.f('fk_anime_deleted_by_users'), 'anime', 'users', ['deleted_by'], ['id'], ondelete='SET NULL')
    
    # Extend episodes table with ownership, locks, and soft delete
    op.add_column('episodes', sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('episodes', sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('episodes', sa.Column('source', sa.String(length=50), server_default='manual', nullable=False))
    op.add_column('episodes', sa.Column('is_locked', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('episodes', sa.Column('locked_fields', postgresql.ARRAY(sa.String(length=100)), nullable=True))
    op.add_column('episodes', sa.Column('locked_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('episodes', sa.Column('locked_reason', sa.Text(), nullable=True))
    op.add_column('episodes', sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('episodes', sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('episodes', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('episodes', sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('episodes', sa.Column('delete_reason', sa.Text(), nullable=True))
    op.add_column('episodes', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    
    op.create_index('ix_episodes_is_deleted', 'episodes', ['is_deleted'], unique=False)
    op.create_foreign_key(op.f('fk_episodes_created_by_users'), 'episodes', 'users', ['created_by'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(op.f('fk_episodes_updated_by_users'), 'episodes', 'users', ['updated_by'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(op.f('fk_episodes_locked_by_users'), 'episodes', 'users', ['locked_by'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(op.f('fk_episodes_deleted_by_users'), 'episodes', 'users', ['deleted_by'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Revert schema changes."""
    # Drop foreign keys and columns from episodes
    op.drop_constraint(op.f('fk_episodes_deleted_by_users'), 'episodes', type_='foreignkey')
    op.drop_constraint(op.f('fk_episodes_locked_by_users'), 'episodes', type_='foreignkey')
    op.drop_constraint(op.f('fk_episodes_updated_by_users'), 'episodes', type_='foreignkey')
    op.drop_constraint(op.f('fk_episodes_created_by_users'), 'episodes', type_='foreignkey')
    op.drop_index('ix_episodes_is_deleted', table_name='episodes')
    op.drop_column('episodes', 'updated_at')
    op.drop_column('episodes', 'delete_reason')
    op.drop_column('episodes', 'deleted_by')
    op.drop_column('episodes', 'deleted_at')
    op.drop_column('episodes', 'is_deleted')
    op.drop_column('episodes', 'locked_at')
    op.drop_column('episodes', 'locked_reason')
    op.drop_column('episodes', 'locked_by')
    op.drop_column('episodes', 'locked_fields')
    op.drop_column('episodes', 'is_locked')
    op.drop_column('episodes', 'source')
    op.drop_column('episodes', 'updated_by')
    op.drop_column('episodes', 'created_by')
    
    # Drop foreign keys and columns from anime
    op.drop_constraint(op.f('fk_anime_deleted_by_users'), 'anime', type_='foreignkey')
    op.drop_constraint(op.f('fk_anime_locked_by_users'), 'anime', type_='foreignkey')
    op.drop_constraint(op.f('fk_anime_updated_by_users'), 'anime', type_='foreignkey')
    op.drop_constraint(op.f('fk_anime_created_by_users'), 'anime', type_='foreignkey')
    op.drop_index('ix_anime_is_deleted', table_name='anime')
    op.drop_index('ix_anime_state', table_name='anime')
    op.drop_column('anime', 'updated_at')
    op.drop_column('anime', 'delete_reason')
    op.drop_column('anime', 'deleted_by')
    op.drop_column('anime', 'deleted_at')
    op.drop_column('anime', 'is_deleted')
    op.drop_column('anime', 'locked_at')
    op.drop_column('anime', 'locked_reason')
    op.drop_column('anime', 'locked_by')
    op.drop_column('anime', 'locked_fields')
    op.drop_column('anime', 'is_locked')
    op.drop_column('anime', 'source')
    op.drop_column('anime', 'updated_by')
    op.drop_column('anime', 'created_by')
    op.drop_column('anime', 'state')
    
    # Drop audit_logs table
    op.drop_index('ix_audit_logs_created_at', table_name='audit_logs')
    op.drop_index('ix_audit_logs_entity_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_entity_type', table_name='audit_logs')
    op.drop_index('ix_audit_logs_action', table_name='audit_logs')
    op.drop_index('ix_audit_logs_actor_type', table_name='audit_logs')
    op.drop_index('ix_audit_logs_actor_id', table_name='audit_logs')
    op.drop_table('audit_logs')
    
    # Drop user_roles table
    op.drop_index('ix_user_roles_role_id', table_name='user_roles')
    op.drop_index('ix_user_roles_user_id', table_name='user_roles')
    op.drop_table('user_roles')
    
    # Drop role_permissions table
    op.drop_index('ix_role_permissions_permission_id', table_name='role_permissions')
    op.drop_index('ix_role_permissions_role_id', table_name='role_permissions')
    op.drop_table('role_permissions')
    
    # Drop permissions table
    op.drop_index('ix_permissions_resource', table_name='permissions')
    op.drop_index('ix_permissions_name', table_name='permissions')
    op.drop_table('permissions')
    
    # Drop roles table
    op.drop_index('ix_roles_name', table_name='roles')
    op.drop_table('roles')
