"""
Tests for RBAC contract enforcement (SECURITY-01).

These tests validate the hard security contract defined in rbac_contract.py.
All tests enforce fail-fast behavior - security violations must raise exceptions.
"""
import pytest

from app.auth import rbac_contract


class TestActorTypeValidation:
    """Test actor type validation and enforcement."""

    def test_validate_actor_type_allows_user(self):
        """User actor type should be valid."""
        rbac_contract.validate_actor_type("user")  # Should not raise

    def test_validate_actor_type_allows_system(self):
        """System actor type should be valid."""
        rbac_contract.validate_actor_type("system")  # Should not raise

    def test_validate_actor_type_allows_anonymous(self):
        """Anonymous actor type should be valid."""
        rbac_contract.validate_actor_type("anonymous")  # Should not raise

    def test_validate_actor_type_rejects_invalid(self):
        """Invalid actor types must be rejected."""
        with pytest.raises(ValueError, match="Invalid actor_type"):
            rbac_contract.validate_actor_type("invalid")

    def test_validate_actor_type_rejects_admin(self):
        """'admin' is not an actor type, it's a role."""
        with pytest.raises(ValueError, match="Invalid actor_type"):
            rbac_contract.validate_actor_type("admin")

    def test_validate_actor_type_rejects_empty(self):
        """Empty string should be rejected."""
        with pytest.raises(ValueError, match="Invalid actor_type"):
            rbac_contract.validate_actor_type("")


class TestRoleValidation:
    """Test role validation and actor type compatibility."""

    def test_user_roles_defined(self):
        """User roles should be defined in contract."""
        expected_user_roles = {"super_admin", "admin", "moderator", "editor", "support", "user"}
        assert rbac_contract.USER_ROLES == expected_user_roles

    def test_system_roles_defined(self):
        """System roles should be defined in contract."""
        expected_system_roles = {"parser_bot", "worker_bot"}
        assert rbac_contract.SYSTEM_ROLES == expected_system_roles

    def test_user_role_with_user_actor(self):
        """User roles can be assigned to user actors."""
        for role in rbac_contract.USER_ROLES:
            rbac_contract.validate_role_for_actor_type(role, "user")  # Should not raise

    def test_system_role_with_system_actor(self):
        """System roles can be assigned to system actors."""
        for role in rbac_contract.SYSTEM_ROLES:
            rbac_contract.validate_role_for_actor_type(role, "system")  # Should not raise

    def test_user_role_with_system_actor_fails(self):
        """User roles CANNOT be assigned to system actors."""
        with pytest.raises(ValueError, match="SECURITY VIOLATION.*Cannot assign user role"):
            rbac_contract.validate_role_for_actor_type("admin", "system")

    def test_system_role_with_user_actor_fails(self):
        """System roles CANNOT be assigned to user actors."""
        with pytest.raises(ValueError, match="SECURITY VIOLATION.*Cannot assign system role"):
            rbac_contract.validate_role_for_actor_type("parser_bot", "user")

    def test_invalid_role_fails(self):
        """Invalid roles must be rejected."""
        with pytest.raises(ValueError, match="Invalid role"):
            rbac_contract.validate_role_for_actor_type("invalid_role", "user")


class TestPermissionValidation:
    """Test permission validation and wildcard prevention."""

    def test_validate_permission_allows_anime_view(self):
        """Explicit anime.view permission should be valid."""
        rbac_contract.validate_permission("anime.view")  # Should not raise

    def test_validate_permission_allows_admin_parser_settings(self):
        """Explicit admin.parser.settings permission should be valid."""
        rbac_contract.validate_permission("admin.parser.settings")  # Should not raise

    def test_validate_permission_rejects_admin_wildcard(self):
        """Wildcard admin:* permission must be rejected."""
        with pytest.raises(ValueError, match="SECURITY VIOLATION.*Wildcard permission.*FORBIDDEN"):
            rbac_contract.validate_permission("admin:*")

    def test_validate_permission_rejects_parser_wildcard(self):
        """Wildcard parser:* permission must be rejected."""
        with pytest.raises(ValueError, match="SECURITY VIOLATION.*Wildcard permission.*FORBIDDEN"):
            rbac_contract.validate_permission("parser:*")

    def test_validate_permission_rejects_system_wildcard(self):
        """Wildcard system:* permission must be rejected."""
        with pytest.raises(ValueError, match="SECURITY VIOLATION.*Wildcard permission.*FORBIDDEN"):
            rbac_contract.validate_permission("system:*")

    def test_validate_permission_rejects_dotstar_wildcard(self):
        """Wildcard .* permission must be rejected."""
        with pytest.raises(ValueError, match="SECURITY VIOLATION.*Wildcard permission.*FORBIDDEN"):
            rbac_contract.validate_permission("admin.*")

    def test_validate_permission_rejects_unknown(self):
        """Unknown permissions must be rejected."""
        with pytest.raises(ValueError, match="Invalid permission"):
            rbac_contract.validate_permission("unknown.permission")

    def test_all_allowed_permissions_are_explicit(self):
        """All allowed permissions must be explicit (no wildcards)."""
        for permission in rbac_contract.ALLOWED_PERMISSIONS:
            assert "*" not in permission, f"Wildcard found in permission: {permission}"
            assert not permission.endswith(".*"), f"Dotstar wildcard in: {permission}"
            assert not permission.endswith(":*"), f"Colon wildcard in: {permission}"


class TestHardInvariants:
    """Test hard invariants enforcement."""

    def test_parser_not_equal_admin_system_actor(self):
        """HARD INVARIANT: System actors CANNOT use admin permissions."""
        with pytest.raises(PermissionError, match="SECURITY VIOLATION.*System actor cannot use admin permission"):
            rbac_contract.check_system_cannot_use_admin_permissions("system", "admin.parser.settings")

    def test_parser_not_equal_admin_user_actor_allowed(self):
        """User actors CAN use admin permissions."""
        # Should not raise
        rbac_contract.check_system_cannot_use_admin_permissions("user", "admin.parser.settings")

    def test_parser_not_equal_admin_system_actor_non_admin_permission(self):
        """System actors CAN use non-admin permissions."""
        # Should not raise
        rbac_contract.check_system_cannot_use_admin_permissions("system", "anime.view")

    def test_no_implicit_permissions_ignores_role(self):
        """HARD INVARIANT: Role status is ignored, only explicit permission matters."""
        # Having a role doesn't grant permission
        result = rbac_contract.check_no_implicit_permissions(has_role=True, has_explicit_permission=False)
        assert result is False

        # Explicit permission is required
        result = rbac_contract.check_no_implicit_permissions(has_role=True, has_explicit_permission=True)
        assert result is True

        # Even without role, explicit permission grants access
        result = rbac_contract.check_no_implicit_permissions(has_role=False, has_explicit_permission=True)
        assert result is True


class TestRolePermissionMappings:
    """Test role-permission mappings in the contract."""

    def test_super_admin_has_all_admin_permissions(self):
        """Super admin should have all admin permissions."""
        super_admin_perms = rbac_contract.ROLE_PERMISSION_MAPPINGS["super_admin"]
        for admin_perm in rbac_contract.ADMIN_PERMISSIONS:
            assert admin_perm in super_admin_perms, f"super_admin missing {admin_perm}"

    def test_parser_bot_has_no_admin_permissions(self):
        """SECURITY: parser_bot must NOT have any admin permissions."""
        parser_perms = rbac_contract.ROLE_PERMISSION_MAPPINGS["parser_bot"]
        admin_perms_in_parser = parser_perms & rbac_contract.ADMIN_PERMISSIONS
        assert len(admin_perms_in_parser) == 0, f"parser_bot has FORBIDDEN admin permissions: {admin_perms_in_parser}"

    def test_worker_bot_has_no_admin_permissions(self):
        """SECURITY: worker_bot must NOT have any admin permissions."""
        worker_perms = rbac_contract.ROLE_PERMISSION_MAPPINGS["worker_bot"]
        admin_perms_in_worker = worker_perms & rbac_contract.ADMIN_PERMISSIONS
        assert len(admin_perms_in_worker) == 0, f"worker_bot has FORBIDDEN admin permissions: {admin_perms_in_worker}"

    def test_all_system_roles_have_no_admin_permissions(self):
        """SECURITY: NO system role can have admin permissions."""
        for role_name in rbac_contract.SYSTEM_ROLES:
            role_perms = rbac_contract.ROLE_PERMISSION_MAPPINGS.get(role_name, frozenset())
            admin_perms = role_perms & rbac_contract.ADMIN_PERMISSIONS
            assert len(admin_perms) == 0, f"System role {role_name} has FORBIDDEN admin permissions: {admin_perms}"

    def test_all_mapped_permissions_are_valid(self):
        """All permissions in mappings must be in ALLOWED_PERMISSIONS."""
        for role_name, perms in rbac_contract.ROLE_PERMISSION_MAPPINGS.items():
            for perm in perms:
                assert perm in rbac_contract.ALLOWED_PERMISSIONS, f"Role {role_name} has invalid permission: {perm}"

    def test_no_wildcard_permissions_in_mappings(self):
        """No wildcard permissions should exist in any role mapping."""
        for role_name, perms in rbac_contract.ROLE_PERMISSION_MAPPINGS.items():
            for perm in perms:
                assert "*" not in perm, f"Wildcard permission in {role_name}: {perm}"


class TestContractValidation:
    """Test that the contract validates itself at module load."""

    def test_contract_validation_runs(self):
        """The contract should validate itself when imported."""
        # If we can import rbac_contract without error, validation passed
        import app.auth.rbac_contract
        assert app.auth.rbac_contract is not None

    def test_all_roles_are_in_mappings(self):
        """All defined roles should have permission mappings."""
        for role in rbac_contract.ALL_ROLES:
            assert role in rbac_contract.ROLE_PERMISSION_MAPPINGS, f"Role {role} missing from mappings"


class TestSecurityBoundaries:
    """Test security boundary enforcement."""

    def test_allowed_permissions_are_immutable(self):
        """ALLOWED_PERMISSIONS should be a frozen set."""
        assert isinstance(rbac_contract.ALLOWED_PERMISSIONS, frozenset)

    def test_user_roles_are_immutable(self):
        """USER_ROLES should be a frozen set."""
        assert isinstance(rbac_contract.USER_ROLES, frozenset)

    def test_system_roles_are_immutable(self):
        """SYSTEM_ROLES should be a frozen set."""
        assert isinstance(rbac_contract.SYSTEM_ROLES, frozenset)

    def test_role_permission_mappings_use_frozen_sets(self):
        """All values in ROLE_PERMISSION_MAPPINGS should be frozen sets."""
        for role, perms in rbac_contract.ROLE_PERMISSION_MAPPINGS.items():
            assert isinstance(perms, frozenset), f"Role {role} permissions not frozen"

    def test_actor_types_are_immutable(self):
        """ALLOWED_ACTOR_TYPES should be a frozen set."""
        assert isinstance(rbac_contract.ALLOWED_ACTOR_TYPES, frozenset)


class TestExplicitPermissions:
    """Test that all required explicit permissions are defined."""

    def test_admin_parser_settings_exists(self):
        """admin.parser.settings must exist (no wildcard)."""
        assert "admin.parser.settings" in rbac_contract.ALLOWED_PERMISSIONS

    def test_admin_parser_emergency_exists(self):
        """admin.parser.emergency must exist (no wildcard)."""
        assert "admin.parser.emergency" in rbac_contract.ALLOWED_PERMISSIONS

    def test_admin_parser_logs_exists(self):
        """admin.parser.logs must exist (no wildcard)."""
        assert "admin.parser.logs" in rbac_contract.ALLOWED_PERMISSIONS

    def test_security_unban_ip_exists(self):
        """security.unban.ip must exist per SECURITY-01."""
        assert "security.unban.ip" in rbac_contract.ALLOWED_PERMISSIONS

    def test_anime_permissions_complete(self):
        """All standard anime CRUD permissions should exist."""
        required = {"anime.view", "anime.create", "anime.edit", "anime.delete", "anime.publish", "anime.lock", "anime.unlock"}
        for perm in required:
            assert perm in rbac_contract.ALLOWED_PERMISSIONS, f"Missing anime permission: {perm}"

    def test_episode_permissions_complete(self):
        """All standard episode CRUD permissions should exist."""
        required = {"episode.view", "episode.create", "episode.edit", "episode.delete", "episode.lock", "episode.unlock"}
        for perm in required:
            assert perm in rbac_contract.ALLOWED_PERMISSIONS, f"Missing episode permission: {perm}"

    def test_audit_view_exists(self):
        """audit.view permission must exist."""
        assert "audit.view" in rbac_contract.ALLOWED_PERMISSIONS
