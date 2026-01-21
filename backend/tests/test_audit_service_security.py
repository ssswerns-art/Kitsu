"""
Tests for AuditService actor_type validation (SECURITY-01).

These tests validate that AuditService properly validates actor_type
and provides security audit logging capabilities.
"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.audit.audit_service import AuditService
from app.models.user import User


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
def audit_service(mock_session):
    """Create an AuditService with mocked session."""
    service = AuditService(mock_session)
    service.audit_repo = MagicMock()
    service.audit_repo.create = AsyncMock()
    return service


class TestAuditServiceActorTypeValidation:
    """Test actor_type validation in AuditService."""

    @pytest.mark.anyio
    async def test_log_validates_user_actor_type(self, audit_service, mock_user):
        """log() should accept 'user' actor_type."""
        await audit_service.log(
            action="anime.edit",
            entity_type="anime",
            entity_id="test-id",
            actor=mock_user,
            actor_type="user"
        )
        # Should not raise

    @pytest.mark.anyio
    async def test_log_validates_system_actor_type(self, audit_service):
        """log() should accept 'system' actor_type."""
        await audit_service.log(
            action="anime.edit",
            entity_type="anime",
            entity_id="test-id",
            actor=None,
            actor_type="system"
        )
        # Should not raise

    @pytest.mark.anyio
    async def test_log_validates_anonymous_actor_type(self, audit_service):
        """log() should accept 'anonymous' actor_type."""
        await audit_service.log(
            action="anime.view",
            entity_type="anime",
            entity_id="test-id",
            actor=None,
            actor_type="anonymous"
        )
        # Should not raise

    @pytest.mark.anyio
    async def test_log_rejects_invalid_actor_type(self, audit_service, mock_user):
        """log() should reject invalid actor_type."""
        with pytest.raises(ValueError, match="Invalid actor_type"):
            await audit_service.log(
                action="anime.edit",
                entity_type="anime",
                entity_id="test-id",
                actor=mock_user,
                actor_type="invalid"
            )

    @pytest.mark.anyio
    async def test_log_rejects_admin_as_actor_type(self, audit_service, mock_user):
        """log() should reject 'admin' as actor_type (it's a role, not actor type)."""
        with pytest.raises(ValueError, match="Invalid actor_type"):
            await audit_service.log(
                action="anime.edit",
                entity_type="anime",
                entity_id="test-id",
                actor=mock_user,
                actor_type="admin"
            )

    @pytest.mark.anyio
    async def test_log_create_validates_actor_type(self, audit_service, mock_user):
        """log_create() should validate actor_type."""
        await audit_service.log_create(
            entity_type="anime",
            entity_id="test-id",
            entity_data={"title": "Test"},
            actor=mock_user,
            actor_type="user"
        )
        # Should not raise

    @pytest.mark.anyio
    async def test_log_update_validates_actor_type(self, audit_service, mock_user):
        """log_update() should validate actor_type."""
        await audit_service.log_update(
            entity_type="anime",
            entity_id="test-id",
            before_data={"title": "Old"},
            after_data={"title": "New"},
            actor=mock_user,
            actor_type="user"
        )
        # Should not raise

    @pytest.mark.anyio
    async def test_log_delete_validates_actor_type(self, audit_service, mock_user):
        """log_delete() should validate actor_type."""
        await audit_service.log_delete(
            entity_type="anime",
            entity_id="test-id",
            entity_data={"title": "Deleted"},
            actor=mock_user,
            actor_type="user"
        )
        # Should not raise


class TestAuditServiceSecurityLogging:
    """Test security-specific audit logging methods."""

    @pytest.mark.anyio
    async def test_log_permission_denied_creates_audit_log(self, audit_service, mock_user):
        """log_permission_denied() should create audit log with proper action."""
        await audit_service.log_permission_denied(
            permission="anime.edit",
            actor=mock_user,
            actor_type="user",
            resource="anime/123"
        )
        
        # Verify create was called
        audit_service.audit_repo.create.assert_called_once()
        call_args = audit_service.audit_repo.create.call_args[1]
        
        assert call_args["action"] == "security.permission_denied"
        assert call_args["entity_type"] == "permission"
        assert call_args["entity_id"] == "anime.edit"
        assert call_args["actor_type"] == "user"

    @pytest.mark.anyio
    async def test_log_permission_denied_validates_actor_type(self, audit_service, mock_user):
        """log_permission_denied() should validate actor_type."""
        with pytest.raises(ValueError, match="Invalid actor_type"):
            await audit_service.log_permission_denied(
                permission="anime.edit",
                actor=mock_user,
                actor_type="invalid"
            )

    @pytest.mark.anyio
    async def test_log_privilege_escalation_attempt_creates_audit_log(self, audit_service, mock_user):
        """log_privilege_escalation_attempt() should create audit log."""
        await audit_service.log_privilege_escalation_attempt(
            actor=mock_user,
            actor_type="user",
            attempted_role="admin",
            attempted_permission="admin.users.manage"
        )
        
        # Verify create was called
        audit_service.audit_repo.create.assert_called_once()
        call_args = audit_service.audit_repo.create.call_args[1]
        
        assert call_args["action"] == "security.escalation_attempt"
        assert call_args["entity_type"] == "security"
        assert call_args["entity_id"] == "privilege_escalation"
        assert call_args["actor_type"] == "user"

    @pytest.mark.anyio
    async def test_log_privilege_escalation_validates_actor_type(self, audit_service, mock_user):
        """log_privilege_escalation_attempt() should validate actor_type."""
        with pytest.raises(ValueError, match="Invalid actor_type"):
            await audit_service.log_privilege_escalation_attempt(
                actor=mock_user,
                actor_type="invalid",
                attempted_role="admin"
            )

    @pytest.mark.anyio
    async def test_log_permission_denied_system_actor(self, audit_service):
        """log_permission_denied() should work for system actors."""
        await audit_service.log_permission_denied(
            permission="admin.parser.settings",
            actor=None,
            actor_type="system",
            resource="parser"
        )
        
        # Verify create was called with system actor_type
        call_args = audit_service.audit_repo.create.call_args[1]
        assert call_args["actor_type"] == "system"
        assert call_args["actor_id"] is None


class TestAuditServiceSystemActions:
    """Test that system actions are properly logged with system actor_type."""

    @pytest.mark.anyio
    async def test_system_action_uses_system_actor_type(self, audit_service):
        """System actions should use actor_type='system'."""
        await audit_service.log(
            action="anime.create",
            entity_type="anime",
            entity_id="test-id",
            actor=None,
            actor_type="system"
        )
        
        call_args = audit_service.audit_repo.create.call_args[1]
        assert call_args["actor_type"] == "system"
        assert call_args["actor_id"] is None

    @pytest.mark.anyio
    async def test_user_action_uses_user_actor_type(self, audit_service, mock_user):
        """User actions should use actor_type='user'."""
        await audit_service.log(
            action="anime.edit",
            entity_type="anime",
            entity_id="test-id",
            actor=mock_user,
            actor_type="user"
        )
        
        call_args = audit_service.audit_repo.create.call_args[1]
        assert call_args["actor_type"] == "user"
        assert call_args["actor_id"] == mock_user.id
