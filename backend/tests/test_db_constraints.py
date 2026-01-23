"""
Test DB constraints for RBAC junction tables.

This test verifies that the UNIQUE constraints on user_roles and role_permissions
prevent duplicate entries as required by TASK A-6.
"""
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import User, Role, Permission, UserRole, RolePermission


class TestUserRoleUniqueConstraint:
    """Test UNIQUE(user_id, role_id) constraint on user_roles table."""

    @pytest.mark.asyncio
    async def test_duplicate_role_assignment_prevented(self, session):
        """Test that assigning the same role to a user twice raises IntegrityError."""
        # Create user and role
        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            password_hash="hash123",
        )
        role = Role(
            id=uuid.uuid4(),
            name="test_role",
            display_name="Test Role",
        )
        session.add(user)
        session.add(role)
        await session.commit()

        # First assignment should succeed
        user_role1 = UserRole(
            id=uuid.uuid4(),
            user_id=user.id,
            role_id=role.id,
        )
        session.add(user_role1)
        await session.commit()

        # Second assignment with same user_id and role_id should fail
        user_role2 = UserRole(
            id=uuid.uuid4(),  # Different ID
            user_id=user.id,  # Same user
            role_id=role.id,  # Same role
        )
        session.add(user_role2)
        
        with pytest.raises(IntegrityError) as exc_info:
            await session.commit()
        
        assert "uq_user_roles_user_id" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_same_role_different_users_allowed(self, session):
        """Test that the same role can be assigned to different users."""
        # Create two users and one role
        user1 = User(
            id=uuid.uuid4(),
            email="user1@example.com",
            password_hash="hash123",
        )
        user2 = User(
            id=uuid.uuid4(),
            email="user2@example.com",
            password_hash="hash456",
        )
        role = Role(
            id=uuid.uuid4(),
            name="admin",
            display_name="Admin",
        )
        session.add_all([user1, user2, role])
        await session.commit()

        # Assign same role to both users - should succeed
        user_role1 = UserRole(
            id=uuid.uuid4(),
            user_id=user1.id,
            role_id=role.id,
        )
        user_role2 = UserRole(
            id=uuid.uuid4(),
            user_id=user2.id,
            role_id=role.id,
        )
        session.add_all([user_role1, user_role2])
        await session.commit()

        # Verify both assignments exist
        result = await session.execute(
            select(UserRole).where(UserRole.role_id == role.id)
        )
        assignments = result.scalars().all()
        assert len(assignments) == 2

    @pytest.mark.asyncio
    async def test_same_user_different_roles_allowed(self, session):
        """Test that a user can be assigned multiple different roles."""
        # Create one user and two roles
        user = User(
            id=uuid.uuid4(),
            email="user@example.com",
            password_hash="hash123",
        )
        role1 = Role(
            id=uuid.uuid4(),
            name="admin",
            display_name="Admin",
        )
        role2 = Role(
            id=uuid.uuid4(),
            name="moderator",
            display_name="Moderator",
        )
        session.add_all([user, role1, role2])
        await session.commit()

        # Assign both roles to user - should succeed
        user_role1 = UserRole(
            id=uuid.uuid4(),
            user_id=user.id,
            role_id=role1.id,
        )
        user_role2 = UserRole(
            id=uuid.uuid4(),
            user_id=user.id,
            role_id=role2.id,
        )
        session.add_all([user_role1, user_role2])
        await session.commit()

        # Verify both assignments exist
        result = await session.execute(
            select(UserRole).where(UserRole.user_id == user.id)
        )
        assignments = result.scalars().all()
        assert len(assignments) == 2


class TestRolePermissionUniqueConstraint:
    """Test UNIQUE(role_id, permission_id) constraint on role_permissions table."""

    @pytest.mark.asyncio
    async def test_duplicate_permission_grant_prevented(self, session):
        """Test that granting the same permission to a role twice raises IntegrityError."""
        # Create role and permission
        role = Role(
            id=uuid.uuid4(),
            name="editor",
            display_name="Editor",
        )
        permission = Permission(
            id=uuid.uuid4(),
            name="anime.edit",
            display_name="Edit Anime",
            resource="anime",
            action="edit",
        )
        session.add(role)
        session.add(permission)
        await session.commit()

        # First grant should succeed
        role_perm1 = RolePermission(
            id=uuid.uuid4(),
            role_id=role.id,
            permission_id=permission.id,
        )
        session.add(role_perm1)
        await session.commit()

        # Second grant with same role_id and permission_id should fail
        role_perm2 = RolePermission(
            id=uuid.uuid4(),  # Different ID
            role_id=role.id,  # Same role
            permission_id=permission.id,  # Same permission
        )
        session.add(role_perm2)
        
        with pytest.raises(IntegrityError) as exc_info:
            await session.commit()
        
        assert "uq_role_permissions_role_id" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_same_permission_different_roles_allowed(self, session):
        """Test that the same permission can be granted to different roles."""
        # Create two roles and one permission
        role1 = Role(
            id=uuid.uuid4(),
            name="editor",
            display_name="Editor",
        )
        role2 = Role(
            id=uuid.uuid4(),
            name="admin",
            display_name="Admin",
        )
        permission = Permission(
            id=uuid.uuid4(),
            name="anime.edit",
            display_name="Edit Anime",
            resource="anime",
            action="edit",
        )
        session.add_all([role1, role2, permission])
        await session.commit()

        # Grant same permission to both roles - should succeed
        role_perm1 = RolePermission(
            id=uuid.uuid4(),
            role_id=role1.id,
            permission_id=permission.id,
        )
        role_perm2 = RolePermission(
            id=uuid.uuid4(),
            role_id=role2.id,
            permission_id=permission.id,
        )
        session.add_all([role_perm1, role_perm2])
        await session.commit()

        # Verify both grants exist
        result = await session.execute(
            select(RolePermission).where(RolePermission.permission_id == permission.id)
        )
        grants = result.scalars().all()
        assert len(grants) == 2

    @pytest.mark.asyncio
    async def test_same_role_different_permissions_allowed(self, session):
        """Test that a role can be granted multiple different permissions."""
        # Create one role and two permissions
        role = Role(
            id=uuid.uuid4(),
            name="editor",
            display_name="Editor",
        )
        perm1 = Permission(
            id=uuid.uuid4(),
            name="anime.edit",
            display_name="Edit Anime",
            resource="anime",
            action="edit",
        )
        perm2 = Permission(
            id=uuid.uuid4(),
            name="anime.delete",
            display_name="Delete Anime",
            resource="anime",
            action="delete",
        )
        session.add_all([role, perm1, perm2])
        await session.commit()

        # Grant both permissions to role - should succeed
        role_perm1 = RolePermission(
            id=uuid.uuid4(),
            role_id=role.id,
            permission_id=perm1.id,
        )
        role_perm2 = RolePermission(
            id=uuid.uuid4(),
            role_id=role.id,
            permission_id=perm2.id,
        )
        session.add_all([role_perm1, role_perm2])
        await session.commit()

        # Verify both grants exist
        result = await session.execute(
            select(RolePermission).where(RolePermission.role_id == role.id)
        )
        grants = result.scalars().all()
        assert len(grants) == 2
