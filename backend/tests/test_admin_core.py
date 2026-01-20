"""
Tests for Admin Core functionality.

This test suite verifies the core admin functionality including:
- Role and permission management
- Audit logging
- Lock mechanism
- Soft delete
"""
import pytest
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException

from app.models.role import Role
from app.models.permission import Permission
from app.models.user_role import UserRole
from app.models.role_permission import RolePermission
from app.models.audit_log import AuditLog
from app.models.anime import Anime
from app.models.episode import Episode
from app.crud.role import RoleRepository
from app.crud.permission import PermissionRepository
from app.crud.audit_log import AuditLogRepository
from app.services.admin import PermissionService, LockService
from app.services.audit import AuditService


class TestRoleModel:
    """Test Role model basic functionality."""
    
    def test_role_creation(self):
        """Test creating a role."""
        role = Role(
            name="test_role",
            display_name="Test Role",
            description="Test role description",
            is_system=False,
            is_active=True
        )
        assert role.name == "test_role"
        assert role.display_name == "Test Role"
        assert role.is_system is False
        assert role.is_active is True


class TestPermissionModel:
    """Test Permission model basic functionality."""
    
    def test_permission_creation(self):
        """Test creating a permission."""
        permission = Permission(
            name="test.view",
            display_name="Test View",
            resource="test",
            action="view",
            description="View test resources",
            is_system=True
        )
        assert permission.name == "test.view"
        assert permission.resource == "test"
        assert permission.action == "view"
        assert permission.is_system is True


class TestAuditLogModel:
    """Test AuditLog model basic functionality."""
    
    def test_audit_log_creation(self):
        """Test creating an audit log entry."""
        actor_id = uuid.uuid4()
        entity_id = uuid.uuid4()
        
        audit_log = AuditLog(
            actor_id=actor_id,
            actor_type="user",
            action="anime.edit",
            entity_type="anime",
            entity_id=str(entity_id),
            before={"title": "Old Title"},
            after={"title": "New Title"},
            reason="Updated title",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0"
        )
        
        assert audit_log.actor_id == actor_id
        assert audit_log.actor_type == "user"
        assert audit_log.action == "anime.edit"
        assert audit_log.entity_type == "anime"
        assert audit_log.before == {"title": "Old Title"}
        assert audit_log.after == {"title": "New Title"}


class TestAnimeExtendedFields:
    """Test Anime model extended fields."""
    
    def test_anime_ownership_fields(self):
        """Test anime ownership fields."""
        user_id = uuid.uuid4()
        anime = Anime(
            title="Test Anime",
            created_by=user_id,
            updated_by=user_id,
            source="manual"
        )
        
        assert anime.created_by == user_id
        assert anime.updated_by == user_id
        assert anime.source == "manual"
    
    def test_anime_lock_fields(self):
        """Test anime lock mechanism fields."""
        user_id = uuid.uuid4()
        anime = Anime(
            title="Test Anime",
            is_locked=True,
            locked_fields=["title", "description"],
            locked_by=user_id,
            locked_reason="Official content",
            locked_at=datetime.now(timezone.utc)
        )
        
        assert anime.is_locked is True
        assert anime.locked_fields == ["title", "description"]
        assert anime.locked_by == user_id
        assert anime.locked_reason == "Official content"
    
    def test_anime_soft_delete_fields(self):
        """Test anime soft delete fields."""
        user_id = uuid.uuid4()
        anime = Anime(
            title="Test Anime",
            is_deleted=True,
            deleted_by=user_id,
            delete_reason="Duplicate entry",
            deleted_at=datetime.now(timezone.utc)
        )
        
        assert anime.is_deleted is True
        assert anime.deleted_by == user_id
        assert anime.delete_reason == "Duplicate entry"
    
    def test_anime_state_machine(self):
        """Test anime state field."""
        anime = Anime(
            title="Test Anime",
            state="draft"
        )
        assert anime.state == "draft"


class TestEpisodeExtendedFields:
    """Test Episode model extended fields."""
    
    def test_episode_ownership_fields(self):
        """Test episode ownership fields."""
        user_id = uuid.uuid4()
        release_id = uuid.uuid4()
        episode = Episode(
            release_id=release_id,
            number=1,
            created_by=user_id,
            updated_by=user_id,
            source="manual"
        )
        
        assert episode.created_by == user_id
        assert episode.updated_by == user_id
        assert episode.source == "manual"
    
    def test_episode_lock_fields(self):
        """Test episode lock mechanism fields."""
        user_id = uuid.uuid4()
        release_id = uuid.uuid4()
        episode = Episode(
            release_id=release_id,
            number=1,
            is_locked=True,
            locked_by=user_id
        )
        
        assert episode.is_locked is True
        assert episode.locked_by == user_id


class TestLockService:
    """Test LockService functionality."""
    
    def test_check_lock_unlocked_entity(self):
        """Test that unlocked entity allows updates."""
        anime = Anime(
            title="Test Anime",
            is_locked=False
        )
        
        # Should not raise exception
        LockService.check_lock(
            entity=anime,
            fields_to_update=["description"],
            actor=None,
            has_override_permission=False
        )
    
    def test_check_lock_fully_locked(self):
        """Test that fully locked entity prevents updates."""
        anime = Anime(
            title="Test Anime",
            is_locked=True,
            locked_fields=None,  # Fully locked
            locked_reason="Official content"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            LockService.check_lock(
                entity=anime,
                fields_to_update=["description"],
                actor=None,
                has_override_permission=False
            )
        
        assert exc_info.value.status_code == 423  # HTTP 423 Locked
    
    def test_check_lock_partially_locked(self):
        """Test partially locked entity."""
        anime = Anime(
            title="Test Anime",
            is_locked=True,
            locked_fields=["title"],
            locked_reason="Official title"
        )
        
        # Updating non-locked field should work
        LockService.check_lock(
            entity=anime,
            fields_to_update=["description"],
            actor=None,
            has_override_permission=False
        )
        
        # Updating locked field should fail
        with pytest.raises(HTTPException) as exc_info:
            LockService.check_lock(
                entity=anime,
                fields_to_update=["title"],
                actor=None,
                has_override_permission=False
            )
        
        assert exc_info.value.status_code == 423
    
    def test_check_lock_with_override(self):
        """Test that override permission bypasses lock."""
        anime = Anime(
            title="Test Anime",
            is_locked=True,
            locked_fields=None,
            locked_reason="Official content"
        )
        
        # Should not raise exception with override
        LockService.check_lock(
            entity=anime,
            fields_to_update=["description"],
            actor=None,
            has_override_permission=True
        )
    
    def test_check_parser_update_manual_content(self):
        """Test parser cannot update manual content."""
        anime = Anime(
            title="Test Anime",
            source="manual"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            LockService.check_parser_update(
                entity=anime,
                fields_to_update=["description"],
                actor_type="system"
            )
        
        assert exc_info.value.status_code == 403
    
    def test_check_parser_update_locked_content(self):
        """Test parser cannot update locked content."""
        anime = Anime(
            title="Test Anime",
            source="parser",
            is_locked=True
        )
        
        with pytest.raises(HTTPException) as exc_info:
            LockService.check_parser_update(
                entity=anime,
                fields_to_update=["description"],
                actor_type="system"
            )
        
        assert exc_info.value.status_code == 423
    
    def test_serialize_entity(self):
        """Test entity serialization for audit logging."""
        anime = Anime(
            title="Test Anime",
            state="draft",
            source="manual"
        )
        
        serialized = LockService.serialize_entity(anime)
        
        assert isinstance(serialized, dict)
        assert serialized.get("title") == "Test Anime"
        assert serialized.get("state") == "draft"
        assert serialized.get("source") == "manual"
