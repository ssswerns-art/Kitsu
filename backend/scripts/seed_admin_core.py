"""
Seed data for default roles and permissions in the admin core system.
This script should be run once after the initial migration to populate the database.

SECURITY: This seed data implements the RBAC contract from rbac_contract.py.
All roles, permissions, and mappings MUST comply with SECURITY-01 requirements.

Usage:
    python -m scripts.seed_admin_core
"""
import asyncio
import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal
from app.crud.role import RoleRepository
from app.crud.permission import PermissionRepository
from app.auth import rbac_contract


# Default system roles per SECURITY-01 contract
DEFAULT_ROLES = [
    # User roles (actor_type="user")
    {
        "name": "super_admin",
        "display_name": "Super Administrator",
        "description": "Full system access with all permissions",
        "is_system": True,
    },
    {
        "name": "admin",
        "display_name": "Administrator",
        "description": "Administrative access to manage content and users",
        "is_system": True,
    },
    {
        "name": "moderator",
        "display_name": "Moderator",
        "description": "Can moderate content and handle user reports",
        "is_system": True,
    },
    {
        "name": "editor",
        "display_name": "Editor",
        "description": "Can create and edit content",
        "is_system": True,
    },
    {
        "name": "support",
        "display_name": "Support",
        "description": "Can view audit logs and help users",
        "is_system": True,
    },
    {
        "name": "user",
        "display_name": "User",
        "description": "Regular user with read access",
        "is_system": True,
    },
    # System roles (actor_type="system")
    {
        "name": "parser_bot",
        "display_name": "Parser Bot",
        "description": "System role for automated parser",
        "is_system": True,
    },
    {
        "name": "worker_bot",
        "display_name": "Worker Bot",
        "description": "System role for background workers",
        "is_system": True,
    },
]

# Default system permissions per SECURITY-01 contract
# SECURITY: NO wildcards (admin:*, parser:*, system:*) are allowed
DEFAULT_PERMISSIONS = [
    # Anime permissions
    {"name": "anime.view", "display_name": "View Anime", "resource": "anime", "action": "view", "description": "View anime entries"},
    {"name": "anime.create", "display_name": "Create Anime", "resource": "anime", "action": "create", "description": "Create new anime entries"},
    {"name": "anime.edit", "display_name": "Edit Anime", "resource": "anime", "action": "edit", "description": "Edit existing anime entries"},
    {"name": "anime.delete", "display_name": "Delete Anime", "resource": "anime", "action": "delete", "description": "Delete anime entries"},
    {"name": "anime.publish", "display_name": "Publish Anime", "resource": "anime", "action": "publish", "description": "Publish anime entries"},
    {"name": "anime.lock", "display_name": "Lock Anime", "resource": "anime", "action": "lock", "description": "Lock anime entries from editing"},
    {"name": "anime.unlock", "display_name": "Unlock Anime", "resource": "anime", "action": "unlock", "description": "Unlock locked anime entries"},
    
    # Episode permissions
    {"name": "episode.view", "display_name": "View Episodes", "resource": "episode", "action": "view", "description": "View episodes"},
    {"name": "episode.create", "display_name": "Create Episodes", "resource": "episode", "action": "create", "description": "Create new episodes"},
    {"name": "episode.edit", "display_name": "Edit Episodes", "resource": "episode", "action": "edit", "description": "Edit existing episodes"},
    {"name": "episode.delete", "display_name": "Delete Episodes", "resource": "episode", "action": "delete", "description": "Delete episodes"},
    {"name": "episode.lock", "display_name": "Lock Episodes", "resource": "episode", "action": "lock", "description": "Lock episodes from editing"},
    {"name": "episode.unlock", "display_name": "Unlock Episodes", "resource": "episode", "action": "unlock", "description": "Unlock locked episodes"},
    
    # Parser permissions (system-specific)
    {"name": "parser.run", "display_name": "Run Parser", "resource": "parser", "action": "run", "description": "Execute parser jobs"},
    {"name": "parser.configure", "display_name": "Configure Parser", "resource": "parser", "action": "configure", "description": "Configure parser settings"},
    {"name": "parser.override_lock", "display_name": "Override Locks", "resource": "parser", "action": "override_lock", "description": "Override content locks as parser"},
    
    # Admin permissions (explicit only, NO wildcards)
    {"name": "admin.parser.settings", "display_name": "Parser Settings", "resource": "admin", "action": "parser.settings", "description": "Manage parser settings"},
    {"name": "admin.parser.emergency", "display_name": "Parser Emergency", "resource": "admin", "action": "parser.emergency", "description": "Emergency parser controls"},
    {"name": "admin.parser.logs", "display_name": "Parser Logs", "resource": "admin", "action": "parser.logs", "description": "View parser logs"},
    {"name": "admin.roles.manage", "display_name": "Manage Roles", "resource": "admin", "action": "roles.manage", "description": "Manage roles and permissions"},
    {"name": "admin.users.manage", "display_name": "Manage Users", "resource": "admin", "action": "users.manage", "description": "Manage user accounts"},
    {"name": "admin.users.view", "display_name": "View Users", "resource": "admin", "action": "users.view", "description": "View user accounts"},
    
    # Audit permissions
    {"name": "audit.view", "display_name": "View Audit Logs", "resource": "audit", "action": "view", "description": "View audit log entries"},
    
    # Security permissions
    {"name": "security.ban.ip", "display_name": "Ban IP Addresses", "resource": "security", "action": "ban.ip", "description": "Ban IP addresses"},
    {"name": "security.unban.ip", "display_name": "Unban IP Addresses", "resource": "security", "action": "unban.ip", "description": "Unban IP addresses"},
]

# Role-Permission mappings per SECURITY-01 contract
# SECURITY: These mappings are validated against rbac_contract.ROLE_PERMISSION_MAPPINGS
ROLE_PERMISSIONS = {
    "super_admin": [
        # All anime permissions
        "anime.view", "anime.create", "anime.edit", "anime.delete", "anime.publish", "anime.lock", "anime.unlock",
        # All episode permissions
        "episode.view", "episode.create", "episode.edit", "episode.delete", "episode.lock", "episode.unlock",
        # Parser administration (NOT parser.run - that's for system actors)
        "parser.configure", "parser.override_lock",
        # All admin permissions (explicit only)
        "admin.parser.settings", "admin.parser.emergency", "admin.parser.logs",
        "admin.roles.manage", "admin.users.manage", "admin.users.view",
        # Audit
        "audit.view",
        # Security
        "security.ban.ip", "security.unban.ip",
    ],
    "admin": [
        # All anime permissions
        "anime.view", "anime.create", "anime.edit", "anime.delete", "anime.publish", "anime.lock", "anime.unlock",
        # All episode permissions
        "episode.view", "episode.create", "episode.edit", "episode.delete", "episode.lock", "episode.unlock",
        # Parser administration
        "parser.configure",
        # Subset of admin permissions
        "admin.parser.settings", "admin.parser.logs", "admin.users.view",
        # Audit
        "audit.view",
    ],
    "moderator": [
        "anime.view", "anime.edit", "anime.lock",
        "episode.view", "episode.edit", "episode.lock",
        "audit.view",
    ],
    "editor": [
        "anime.view", "anime.create", "anime.edit",
        "episode.view", "episode.create", "episode.edit",
    ],
    "support": [
        "anime.view",
        "episode.view",
        "admin.users.view",
        "audit.view",
    ],
    "user": [
        "anime.view",
        "episode.view",
    ],
    # System roles (actor_type="system")
    # SECURITY: System roles CANNOT have admin.* permissions
    "parser_bot": [
        "anime.view", "anime.create", "anime.edit",
        "episode.view", "episode.create", "episode.edit",
        "parser.run",
        "parser.override_lock",
    ],
    "worker_bot": [
        "anime.view",
        "episode.view",
        "parser.run",
    ],
}


async def seed_admin_core():
    """Seed the database with default roles and permissions per SECURITY-01 contract."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            role_repo = RoleRepository(session)
            permission_repo = PermissionRepository(session)
        
        print("SECURITY-01: Seeding RBAC contract-compliant data...")
        print(f"  Actor types: {', '.join(rbac_contract.ALLOWED_ACTOR_TYPES)}")
        print(f"  User roles: {', '.join(rbac_contract.USER_ROLES)}")
        print(f"  System roles: {', '.join(rbac_contract.SYSTEM_ROLES)}")
        print(f"  Total permissions: {len(rbac_contract.ALLOWED_PERMISSIONS)}")
        
        print("\nSeeding permissions...")
        permission_map = {}
        for perm_data in DEFAULT_PERMISSIONS:
            # SECURITY: Validate permission against contract
            try:
                rbac_contract.validate_permission(perm_data["name"])
            except ValueError as e:
                print(f"  ERROR: Permission '{perm_data['name']}' violates contract: {e}")
                continue
            
            existing = await permission_repo.get_by_name(perm_data["name"])
            if existing:
                print(f"  Permission '{perm_data['name']}' already exists, skipping...")
                permission_map[perm_data["name"]] = existing.id
                continue
            
            permission = await permission_repo.create(
                name=perm_data["name"],
                display_name=perm_data["display_name"],
                resource=perm_data["resource"],
                action=perm_data["action"],
                description=perm_data.get("description"),
                is_system=True,
            )
            permission_map[perm_data["name"]] = permission.id
            print(f"  ✓ Created permission: {perm_data['name']}")
        
        print("\nSeeding roles...")
        role_map = {}
        for role_data in DEFAULT_ROLES:
            # SECURITY: Validate role against contract
            if role_data["name"] not in rbac_contract.ALL_ROLES:
                print(f"  ERROR: Role '{role_data['name']}' not in contract")
                continue
            
            existing = await role_repo.get_by_name(role_data["name"])
            if existing:
                print(f"  Role '{role_data['name']}' already exists, skipping...")
                role_map[role_data["name"]] = existing.id
                continue
            
            role = await role_repo.create(
                name=role_data["name"],
                display_name=role_data["display_name"],
                description=role_data.get("description"),
                is_system=role_data.get("is_system", False),
            )
            role_map[role_data["name"]] = role.id
            
            # Mark role type
            role_type = "USER" if role_data["name"] in rbac_contract.USER_ROLES else "SYSTEM"
            print(f"  ✓ Created role: {role_data['name']} ({role_type})")
        
        print("\nAssigning permissions to roles...")
        for role_name, permission_names in ROLE_PERMISSIONS.items():
            role_id = role_map.get(role_name)
            if not role_id:
                print(f"  Role '{role_name}' not found, skipping permissions...")
                continue
            
            # SECURITY: Validate no system roles have admin permissions
            if role_name in rbac_contract.SYSTEM_ROLES:
                admin_perms = [p for p in permission_names if p in rbac_contract.ADMIN_PERMISSIONS]
                if admin_perms:
                    error_msg = (
                        f"SECURITY-01 VIOLATION: System role '{role_name}' has FORBIDDEN admin permissions: {admin_perms}\n"
                        f"Parser ≠ Admin invariant violated! Seeding aborted."
                    )
                    print(f"  ERROR: {error_msg}")
                    raise RuntimeError(error_msg)
            
            for perm_name in permission_names:
                perm_id = permission_map.get(perm_name)
                if not perm_id:
                    print(f"  Permission '{perm_name}' not found, skipping...")
                    continue
                
                try:
                    await role_repo.assign_permission(role_id, perm_id)
                except Exception as e:
                    print(f"  Warning: Could not assign '{perm_name}' to '{role_name}': {e}")
            
            print(f"  ✓ Assigned {len(permission_names)} permissions to '{role_name}'")
            
            print("\n✅ SECURITY-01: RBAC contract seeding completed successfully!")
            print("\nSECURITY SUMMARY:")
            print("  ✓ No wildcard permissions (admin:*, parser:*, system:*)")
            print("  ✓ System roles separated from user roles")
            print("  ✓ Parser ≠ Admin invariant enforced")
            print("  ✓ All permissions explicit and contract-compliant")


if __name__ == "__main__":
    asyncio.run(seed_admin_core())
