from __future__ import annotations

from typing import Final, Iterable

from ..models.user import User

Role = str
Permission = str

BASE_ROLES: Final[tuple[Role, ...]] = ("guest", "user", "admin")
BASE_PERMISSIONS: Final[tuple[Permission, ...]] = (
    "read:profile",
    "write:profile",
    "read:content",
    "write:content",
    "admin:*",
    "admin:parser.settings",
    "admin:parser.emergency",
    "admin:parser.logs",
)

ROLE_PERMISSIONS: Final[dict[Role, tuple[Permission, ...]]] = {
    "guest": ("read:content",),
    "user": ("read:profile", "write:profile", "read:content", "write:content"),
    "admin": (
        "read:profile",
        "write:profile",
        "read:content",
        "write:content",
        "admin:*",
        "admin:parser.settings",
        "admin:parser.emergency",
        "admin:parser.logs",
    ),
}


def resolve_role(user: User | None) -> Role:
    if user is None:
        return "guest"
    user_role = getattr(user, "role", None)
    if user_role in BASE_ROLES:
        return user_role
    if getattr(user, "is_admin", False) or getattr(user, "is_superuser", False):
        return "admin"
    return "user"


def resolve_permissions(role: Role) -> list[Permission]:
    return list(ROLE_PERMISSIONS.get(role, ()))

