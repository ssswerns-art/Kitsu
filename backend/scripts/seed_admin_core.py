"""
Seed data for default roles and permissions in the admin core system.
This script should be run once after the initial migration to populate the database.

Usage:
    cd /home/runner/work/Kitsu/Kitsu/backend
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


# Default system roles
DEFAULT_ROLES = [
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
        "name": "parser_bot",
        "display_name": "Parser Bot",
        "description": "System role for automated parser",
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
]

# Default system permissions
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
    
    # Parser permissions
    {"name": "parser.run", "display_name": "Run Parser", "resource": "parser", "action": "run", "description": "Execute parser jobs"},
    {"name": "parser.configure", "display_name": "Configure Parser", "resource": "parser", "action": "configure", "description": "Configure parser settings"},
    {"name": "parser.override_lock", "display_name": "Override Locks", "resource": "parser", "action": "override_lock", "description": "Override content locks as parser"},
    
    # Admin permissions
    {"name": "admin.roles.manage", "display_name": "Manage Roles", "resource": "admin", "action": "roles.manage", "description": "Manage roles and permissions"},
    {"name": "admin.users.manage", "display_name": "Manage Users", "resource": "admin", "action": "users.manage", "description": "Manage user accounts"},
    {"name": "admin.users.view", "display_name": "View Users", "resource": "admin", "action": "users.view", "description": "View user accounts"},
    
    # Audit permissions
    {"name": "audit.view", "display_name": "View Audit Logs", "resource": "audit", "action": "view", "description": "View audit log entries"},
    
    # Security permissions
    {"name": "security.ban.ip", "display_name": "Ban IP Addresses", "resource": "security", "action": "ban.ip", "description": "Ban IP addresses"},
]

# Role-Permission mappings
ROLE_PERMISSIONS = {
    "super_admin": [
        "anime.view", "anime.create", "anime.edit", "anime.delete", "anime.publish", "anime.lock", "anime.unlock",
        "episode.view", "episode.create", "episode.edit", "episode.delete", "episode.lock",
        "parser.run", "parser.configure", "parser.override_lock",
        "admin.roles.manage", "admin.users.manage", "admin.users.view",
        "audit.view",
        "security.ban.ip",
    ],
    "admin": [
        "anime.view", "anime.create", "anime.edit", "anime.delete", "anime.publish", "anime.lock", "anime.unlock",
        "episode.view", "episode.create", "episode.edit", "episode.delete", "episode.lock",
        "parser.run", "parser.configure",
        "admin.users.view",
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
    "parser_bot": [
        "anime.view", "anime.create", "anime.edit",
        "episode.view", "episode.create", "episode.edit",
        "parser.run",
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
}


async def seed_admin_core():
    """Seed the database with default roles and permissions."""
    async with AsyncSessionLocal() as session:
        role_repo = RoleRepository(session)
        permission_repo = PermissionRepository(session)
        
        print("Seeding permissions...")
        permission_map = {}
        for perm_data in DEFAULT_PERMISSIONS:
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
            print(f"  Created permission: {perm_data['name']}")
        
        print("\nSeeding roles...")
        role_map = {}
        for role_data in DEFAULT_ROLES:
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
            print(f"  Created role: {role_data['name']}")
        
        print("\nAssigning permissions to roles...")
        for role_name, permission_names in ROLE_PERMISSIONS.items():
            role_id = role_map.get(role_name)
            if not role_id:
                print(f"  Role '{role_name}' not found, skipping permissions...")
                continue
            
            for perm_name in permission_names:
                perm_id = permission_map.get(perm_name)
                if not perm_id:
                    print(f"  Permission '{perm_name}' not found, skipping...")
                    continue
                
                try:
                    await role_repo.assign_permission(role_id, perm_id)
                except Exception as e:
                    print(f"  Warning: Could not assign '{perm_name}' to '{role_name}': {e}")
            
            print(f"  Assigned {len(permission_names)} permissions to '{role_name}'")
        
        print("\n✅ Seeding completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed_admin_core())
