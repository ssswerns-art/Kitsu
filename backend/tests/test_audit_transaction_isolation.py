"""
Tests for audit logging transaction isolation in PermissionService.

These tests validate that audit logging uses a separate session from
the main business transaction, preventing commit leakage.
"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from app.services.admin.permission_service import PermissionService
from app.models.user import User
from fastapi import HTTPException


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession for the main transaction."""
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    return user


@pytest.fixture
def permission_service(mock_session):
    """Create a PermissionService with mocked session."""
    service = PermissionService(mock_session)
    # Mock the permission_repo to return no permissions (will trigger denial)
    service.permission_repo = MagicMock()
    service.permission_repo.get_user_permissions = AsyncMock(return_value=[])
    return service


class TestAuditTransactionIsolation:
    """Test that audit logging uses a separate session from main transaction."""

    @pytest.mark.anyio
    async def test_audit_uses_separate_session(self, permission_service, mock_user, mock_session):
        """Audit logging should create and use its own session, not the main one."""
        
        # Create a mock for the separate audit session
        mock_audit_session = MagicMock()
        mock_audit_session.commit = AsyncMock()
        mock_audit_session.rollback = AsyncMock()
        mock_audit_session.__aenter__ = AsyncMock(return_value=mock_audit_session)
        mock_audit_session.__aexit__ = AsyncMock(return_value=None)
        
        # Patch AsyncSessionLocal to return our mock audit session
        with patch('app.services.admin.permission_service.AsyncSessionLocal') as mock_session_maker:
            mock_session_maker.return_value = mock_audit_session
            
            # Attempt to require a permission that will be denied
            with pytest.raises(HTTPException) as exc_info:
                await permission_service.require_permission(
                    mock_user, 
                    "anime.edit", 
                    actor_type="user"
                )
            
            # Verify 403 is raised
            assert exc_info.value.status_code == 403
            
            # Verify AsyncSessionLocal was called to create a new session
            mock_session_maker.assert_called_once()
            
            # Verify the audit session's commit was called (not the main session)
            mock_audit_session.commit.assert_called_once()
            
            # Verify the main session's commit was NOT called
            mock_session.commit.assert_not_called()

    @pytest.mark.anyio
    async def test_audit_error_does_not_affect_main_transaction(self, permission_service, mock_user, mock_session):
        """Audit logging errors should not affect the permission check or main transaction."""
        
        # Create a mock for the separate audit session that will fail
        mock_audit_session = MagicMock()
        mock_audit_session.commit = AsyncMock(side_effect=Exception("Audit DB error"))
        mock_audit_session.__aenter__ = AsyncMock(return_value=mock_audit_session)
        mock_audit_session.__aexit__ = AsyncMock(return_value=None)
        
        # Patch AsyncSessionLocal to return our mock audit session
        with patch('app.services.admin.permission_service.AsyncSessionLocal') as mock_session_maker:
            mock_session_maker.return_value = mock_audit_session
            
            # Attempt to require a permission that will be denied
            with pytest.raises(HTTPException) as exc_info:
                await permission_service.require_permission(
                    mock_user, 
                    "anime.edit", 
                    actor_type="user"
                )
            
            # Verify 403 is still raised even though audit failed
            assert exc_info.value.status_code == 403
            
            # Verify the main session remains untouched
            mock_session.commit.assert_not_called()
            mock_session.rollback.assert_not_called()

    @pytest.mark.anyio
    async def test_audit_session_context_manager_cleanup(self, permission_service, mock_user, mock_session):
        """Audit session should be properly cleaned up via context manager."""
        
        # Create a mock for the separate audit session
        mock_audit_session = MagicMock()
        mock_audit_session.commit = AsyncMock()
        mock_audit_session.__aenter__ = AsyncMock(return_value=mock_audit_session)
        mock_audit_session.__aexit__ = AsyncMock(return_value=None)
        
        # Patch AsyncSessionLocal
        with patch('app.services.admin.permission_service.AsyncSessionLocal') as mock_session_maker:
            mock_session_maker.return_value = mock_audit_session
            
            # Attempt to require a permission that will be denied
            with pytest.raises(HTTPException):
                await permission_service.require_permission(
                    mock_user, 
                    "anime.edit", 
                    actor_type="user"
                )
            
            # Verify __aenter__ and __aexit__ were called (context manager lifecycle)
            mock_audit_session.__aenter__.assert_called_once()
            mock_audit_session.__aexit__.assert_called_once()

    @pytest.mark.anyio
    async def test_main_session_isolation_preserved(self, permission_service, mock_user, mock_session):
        """Main session should remain completely isolated from audit operations."""
        
        # Track all method calls on the main session
        mock_session.reset_mock()
        
        # Create a mock for the separate audit session
        mock_audit_session = MagicMock()
        mock_audit_session.commit = AsyncMock()
        mock_audit_session.__aenter__ = AsyncMock(return_value=mock_audit_session)
        mock_audit_session.__aexit__ = AsyncMock(return_value=None)
        
        # Patch AsyncSessionLocal
        with patch('app.services.admin.permission_service.AsyncSessionLocal') as mock_session_maker:
            mock_session_maker.return_value = mock_audit_session
            
            # Attempt to require a permission that will be denied
            with pytest.raises(HTTPException):
                await permission_service.require_permission(
                    mock_user, 
                    "anime.edit", 
                    actor_type="user"
                )
            
            # Verify NO transaction-related methods were called on the main session
            # (only permission_repo.get_user_permissions was called earlier)
            mock_session.commit.assert_not_called()
            mock_session.rollback.assert_not_called()
            mock_session.flush.assert_not_called() if hasattr(mock_session, 'flush') else None
