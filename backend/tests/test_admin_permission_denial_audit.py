"""
Tests for AUDIT ISSUE #8: Admin Permission Denial Logging.

This test suite verifies that:
1. Permission denials are logged to audit_logs table
2. Successful permission checks are NOT logged
3. Audit logging failures don't break 403 responses
"""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.contracts.permissions import AdminPermission
from app.admin.dependencies import require_admin_permission, require_admin_permissions
from app.models.user import User


class TestPermissionDenialAudit:
    """Test audit logging for permission denials."""

    @pytest.mark.anyio
    async def test_single_permission_denial_creates_audit_log(self):
        """Test that denying a single permission creates an audit log entry."""
        # Setup
        user_id = uuid.uuid4()
        user = User(id=user_id, email="test@example.com", password_hash="fake")
        
        mock_db = MagicMock(spec=AsyncSession)
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/admin/users"
        
        # Mock PermissionService to return False (permission denied)
        with patch("app.admin.dependencies.PermissionService") as MockPermissionService:
            mock_service = MockPermissionService.return_value
            mock_service.has_permission = AsyncMock(return_value=False)
            
            # Mock AuditLogRepository to capture the audit log call
            with patch("app.admin.dependencies.AuditLogRepository") as MockAuditRepo:
                mock_audit = MockAuditRepo.return_value
                mock_audit.create = AsyncMock()
                
                # Create dependency
                dependency = require_admin_permission(AdminPermission.USERS_VIEW)
                
                # Execute and expect HTTPException
                with pytest.raises(HTTPException) as exc_info:
                    await dependency(request=mock_request, user=user, db=mock_db)
                
                # Verify 403 was raised
                assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
                assert "admin.users.view" in exc_info.value.detail
                
                # Verify audit log was created
                mock_audit.create.assert_called_once()
                call_kwargs = mock_audit.create.call_args.kwargs
                
                assert call_kwargs["actor_id"] == user_id
                assert call_kwargs["actor_type"] == "user"
                assert call_kwargs["action"] == "permission_denied"
                assert call_kwargs["entity_type"] == "admin_permission"
                assert call_kwargs["entity_id"] == "admin.users.view"
                assert call_kwargs["reason"] == "RBAC_DENIED"
                assert call_kwargs["before"] is None
                assert "required_permissions" in call_kwargs["after"]
                assert call_kwargs["after"]["required_permissions"] == ["admin.users.view"]
                assert call_kwargs["after"]["request_method"] == "GET"
                assert call_kwargs["after"]["request_path"] == "/admin/users"

    @pytest.mark.anyio
    async def test_multiple_permissions_denial_creates_audit_log(self):
        """Test that denying multiple permissions creates an audit log entry."""
        # Setup
        user_id = uuid.uuid4()
        user = User(id=user_id, email="test@example.com", password_hash="fake")
        
        mock_db = MagicMock(spec=AsyncSession)
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/admin/roles/assign"
        
        # Mock PermissionService to return False (permission denied)
        with patch("app.admin.dependencies.PermissionService") as MockPermissionService:
            mock_service = MockPermissionService.return_value
            mock_service.has_all_permissions = AsyncMock(return_value=False)
            
            # Mock AuditLogRepository to capture the audit log call
            with patch("app.admin.dependencies.AuditLogRepository") as MockAuditRepo:
                mock_audit = MockAuditRepo.return_value
                mock_audit.create = AsyncMock()
                
                # Create dependency with multiple permissions
                dependency = require_admin_permissions(
                    AdminPermission.USERS_MANAGE,
                    AdminPermission.ROLES_MANAGE
                )
                
                # Execute and expect HTTPException
                with pytest.raises(HTTPException) as exc_info:
                    await dependency(request=mock_request, user=user, db=mock_db)
                
                # Verify 403 was raised
                assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
                
                # Verify audit log was created
                mock_audit.create.assert_called_once()
                call_kwargs = mock_audit.create.call_args.kwargs
                
                assert call_kwargs["actor_id"] == user_id
                assert call_kwargs["actor_type"] == "user"
                assert call_kwargs["action"] == "permission_denied"
                assert call_kwargs["entity_type"] == "admin_permission"
                assert "admin.users.manage" in call_kwargs["entity_id"]
                assert "admin.roles.manage" in call_kwargs["entity_id"]
                assert call_kwargs["reason"] == "RBAC_DENIED"
                assert "required_permissions" in call_kwargs["after"]
                assert "admin.users.manage" in call_kwargs["after"]["required_permissions"]
                assert "admin.roles.manage" in call_kwargs["after"]["required_permissions"]

    @pytest.mark.anyio
    async def test_successful_permission_check_no_audit_log(self):
        """Test that successful permission checks do NOT create audit logs."""
        # Setup
        user_id = uuid.uuid4()
        user = User(id=user_id, email="test@example.com", password_hash="fake")
        
        mock_db = MagicMock(spec=AsyncSession)
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/admin/users"
        
        # Mock PermissionService to return True (permission granted)
        with patch("app.admin.dependencies.PermissionService") as MockPermissionService:
            mock_service = MockPermissionService.return_value
            mock_service.has_permission = AsyncMock(return_value=True)
            
            # Mock AuditLogRepository to verify it's NOT called
            with patch("app.admin.dependencies.AuditLogRepository") as MockAuditRepo:
                mock_audit = MockAuditRepo.return_value
                mock_audit.create = AsyncMock()
                
                # Create dependency
                dependency = require_admin_permission(AdminPermission.USERS_VIEW)
                
                # Execute - should succeed without exception
                await dependency(request=mock_request, user=user, db=mock_db)
                
                # Verify audit log was NOT created
                mock_audit.create.assert_not_called()

    @pytest.mark.anyio
    async def test_audit_failure_still_returns_403(self):
        """Test that audit logging failures don't prevent 403 response."""
        # Setup
        user_id = uuid.uuid4()
        user = User(id=user_id, email="test@example.com", password_hash="fake")
        
        mock_db = MagicMock(spec=AsyncSession)
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/admin/users"
        
        # Mock PermissionService to return False (permission denied)
        with patch("app.admin.dependencies.PermissionService") as MockPermissionService:
            mock_service = MockPermissionService.return_value
            mock_service.has_permission = AsyncMock(return_value=False)
            
            # Mock AuditLogRepository to raise an exception
            with patch("app.admin.dependencies.AuditLogRepository") as MockAuditRepo:
                mock_audit = MockAuditRepo.return_value
                mock_audit.create = AsyncMock(side_effect=Exception("Database error"))
                
                # Create dependency
                dependency = require_admin_permission(AdminPermission.USERS_VIEW)
                
                # Execute and expect HTTPException (not the audit exception)
                with pytest.raises(HTTPException) as exc_info:
                    await dependency(request=mock_request, user=user, db=mock_db)
                
                # Verify 403 was still raised despite audit failure
                assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
                assert "admin.users.view" in exc_info.value.detail
                
                # Verify audit create was attempted
                mock_audit.create.assert_called_once()

    @pytest.mark.anyio
    async def test_multiple_permissions_successful_no_audit(self):
        """Test that successful multiple permission checks do NOT create audit logs."""
        # Setup
        user_id = uuid.uuid4()
        user = User(id=user_id, email="test@example.com", password_hash="fake")
        
        mock_db = MagicMock(spec=AsyncSession)
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/admin/roles/assign"
        
        # Mock PermissionService to return True (permission granted)
        with patch("app.admin.dependencies.PermissionService") as MockPermissionService:
            mock_service = MockPermissionService.return_value
            mock_service.has_all_permissions = AsyncMock(return_value=True)
            
            # Mock AuditLogRepository to verify it's NOT called
            with patch("app.admin.dependencies.AuditLogRepository") as MockAuditRepo:
                mock_audit = MockAuditRepo.return_value
                mock_audit.create = AsyncMock()
                
                # Create dependency with multiple permissions
                dependency = require_admin_permissions(
                    AdminPermission.USERS_MANAGE,
                    AdminPermission.ROLES_MANAGE
                )
                
                # Execute - should succeed without exception
                await dependency(request=mock_request, user=user, db=mock_db)
                
                # Verify audit log was NOT created
                mock_audit.create.assert_not_called()
