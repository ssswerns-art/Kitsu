"""
Tests for PermissionService with RBAC contract enforcement (SECURITY-01).

These tests validate that PermissionService properly enforces hard invariants.
"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.admin.permission_service import PermissionService
from app.models.user import User
from app.models.permission import Permission


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession."""
    return MagicMock()


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    return user


@pytest.fixture
def permission_service(mock_session):
    """Create a PermissionService with mocked session."""
    return PermissionService(mock_session)


class TestPermissionServiceActorTypeValidation:
    """Test actor_type validation in PermissionService."""

    @pytest.mark.anyio
    async def test_has_permission_validates_actor_type(self, permission_service, mock_user):
        """has_permission should validate actor_type."""
        # Valid actor types should not raise
        permission_service.permission_repo = MagicMock()
        permission_service.permission_repo.get_user_permissions = AsyncMock(return_value=[])
        
        await permission_service.has_permission(mock_user, "anime.view", actor_type="user")
        await permission_service.has_permission(mock_user, "anime.view", actor_type="system")
        
        # Invalid actor type should raise
        with pytest.raises(ValueError, match="Invalid actor_type"):
            await permission_service.has_permission(mock_user, "anime.view", actor_type="invalid")

    @pytest.mark.anyio
    async def test_has_permission_anonymous_has_no_permissions(self, permission_service, mock_user):
        """Anonymous actor type should have no permissions."""
        result = await permission_service.has_permission(mock_user, "anime.view", actor_type="anonymous")
        assert result is False

    @pytest.mark.anyio
    async def test_has_permission_none_user_returns_false(self, permission_service):
        """None user should always return False."""
        result = await permission_service.has_permission(None, "anime.view", actor_type="user")
        assert result is False


class TestPermissionServiceWildcardPrevention:
    """Test that PermissionService rejects wildcard permissions."""

    @pytest.mark.anyio
    async def test_has_permission_rejects_admin_wildcard(self, permission_service, mock_user):
        """Wildcard admin:* should be rejected."""
        result = await permission_service.has_permission(mock_user, "admin:*", actor_type="user")
        assert result is False  # Wildcard validation fails, returns False

    @pytest.mark.anyio
    async def test_has_permission_rejects_parser_wildcard(self, permission_service, mock_user):
        """Wildcard parser:* should be rejected."""
        result = await permission_service.has_permission(mock_user, "parser:*", actor_type="user")
        assert result is False

    @pytest.mark.anyio
    async def test_has_permission_rejects_unknown_permission(self, permission_service, mock_user):
        """Unknown permissions should be rejected."""
        result = await permission_service.has_permission(mock_user, "unknown.permission", actor_type="user")
        assert result is False


class TestPermissionServiceHardInvariants:
    """Test hard invariant enforcement in PermissionService."""

    @pytest.mark.anyio
    async def test_system_actor_cannot_use_admin_permissions(self, permission_service, mock_user):
        """HARD INVARIANT: System actors CANNOT use admin permissions."""
        # Even if database grants it, the check should fail
        result = await permission_service.has_permission(
            mock_user, 
            "admin.parser.settings", 
            actor_type="system"
        )
        assert result is False  # Hard invariant prevents this

    @pytest.mark.anyio
    async def test_user_actor_can_use_admin_permissions(self, permission_service, mock_user):
        """User actors CAN use admin permissions if granted."""
        # Mock database returning the permission
        mock_perm = MagicMock(spec=Permission)
        mock_perm.name = "admin.parser.settings"
        
        permission_service.permission_repo = MagicMock()
        permission_service.permission_repo.get_user_permissions = AsyncMock(return_value=[mock_perm])
        
        result = await permission_service.has_permission(
            mock_user,
            "admin.parser.settings",
            actor_type="user"
        )
        assert result is True

    @pytest.mark.anyio
    async def test_system_actor_can_use_non_admin_permissions(self, permission_service, mock_user):
        """System actors CAN use non-admin permissions."""
        # Mock database returning the permission
        mock_perm = MagicMock(spec=Permission)
        mock_perm.name = "anime.view"
        
        permission_service.permission_repo = MagicMock()
        permission_service.permission_repo.get_user_permissions = AsyncMock(return_value=[mock_perm])
        
        result = await permission_service.has_permission(
            mock_user,
            "anime.view",
            actor_type="system"
        )
        assert result is True


class TestPermissionServiceExplicitPermissions:
    """Test that only explicit permissions are granted."""

    @pytest.mark.anyio
    async def test_has_permission_requires_exact_match(self, permission_service, mock_user):
        """Permission check requires exact match, no fuzzy matching."""
        # User has anime.view
        mock_perm = MagicMock(spec=Permission)
        mock_perm.name = "anime.view"
        
        permission_service.permission_repo = MagicMock()
        permission_service.permission_repo.get_user_permissions = AsyncMock(return_value=[mock_perm])
        
        # Exact match succeeds
        result = await permission_service.has_permission(mock_user, "anime.view", actor_type="user")
        assert result is True
        
        # Different permission fails
        result = await permission_service.has_permission(mock_user, "anime.edit", actor_type="user")
        assert result is False

    @pytest.mark.anyio
    async def test_has_any_permission_checks_all(self, permission_service, mock_user):
        """has_any_permission should check all permissions."""
        mock_perm = MagicMock(spec=Permission)
        mock_perm.name = "anime.view"
        
        permission_service.permission_repo = MagicMock()
        permission_service.permission_repo.get_user_permissions = AsyncMock(return_value=[mock_perm])
        
        # Has one of the permissions
        result = await permission_service.has_any_permission(
            mock_user,
            ["anime.edit", "anime.view"],
            actor_type="user"
        )
        assert result is True
        
        # Has none of the permissions
        result = await permission_service.has_any_permission(
            mock_user,
            ["anime.edit", "anime.delete"],
            actor_type="user"
        )
        assert result is False

    @pytest.mark.anyio
    async def test_has_all_permissions_checks_all(self, permission_service, mock_user):
        """has_all_permissions should check all permissions."""
        mock_perm1 = MagicMock(spec=Permission)
        mock_perm1.name = "anime.view"
        mock_perm2 = MagicMock(spec=Permission)
        mock_perm2.name = "anime.edit"
        
        permission_service.permission_repo = MagicMock()
        permission_service.permission_repo.get_user_permissions = AsyncMock(return_value=[mock_perm1, mock_perm2])
        
        # Has all permissions
        result = await permission_service.has_all_permissions(
            mock_user,
            ["anime.view", "anime.edit"],
            actor_type="user"
        )
        assert result is True
        
        # Missing one permission
        result = await permission_service.has_all_permissions(
            mock_user,
            ["anime.view", "anime.edit", "anime.delete"],
            actor_type="user"
        )
        assert result is False


class TestPermissionServiceRequirePermission:
    """Test require_permission enforcement."""

    @pytest.mark.anyio
    async def test_require_permission_raises_403_when_denied(self, permission_service, mock_user):
        """require_permission should raise HTTPException with 403."""
        from fastapi import HTTPException
        
        permission_service.permission_repo = MagicMock()
        permission_service.permission_repo.get_user_permissions = AsyncMock(return_value=[])
        
        with pytest.raises(HTTPException) as exc_info:
            await permission_service.require_permission(mock_user, "anime.edit", actor_type="user")
        
        assert exc_info.value.status_code == 403
        assert "anime.edit" in exc_info.value.detail

    @pytest.mark.anyio
    async def test_require_permission_succeeds_when_granted(self, permission_service, mock_user):
        """require_permission should not raise when permission is granted."""
        mock_perm = MagicMock(spec=Permission)
        mock_perm.name = "anime.edit"
        
        permission_service.permission_repo = MagicMock()
        permission_service.permission_repo.get_user_permissions = AsyncMock(return_value=[mock_perm])
        
        # Should not raise
        await permission_service.require_permission(mock_user, "anime.edit", actor_type="user")
