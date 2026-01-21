"""Declarative mapping of protected endpoints to required permissions.

Each key is a (METHOD, PATH) tuple, and the value is a tuple of permissions
that satisfy the endpoint's RBAC enforcement.

SECURITY: All permissions must be explicit (no wildcards like "admin:*").
Per SECURITY-01 contract, only allowed permissions from rbac_contract.py are valid.
"""
from .helpers import require_permission
from .rbac import Permission

# SECURITY: Wildcard permissions removed per SECURITY-01
# Old entries with "admin:*" replaced with explicit permissions
ENFORCEMENT_MATRIX: dict[tuple[str, str], tuple[Permission, ...]] = {
    ("POST", "/favorites"): ("write:content",),
    ("DELETE", "/favorites/{anime_id}"): ("write:content",),
    ("POST", "/watch/progress"): ("write:content",),
    # Parser admin endpoints now use explicit admin permissions
    ("POST", "/admin/parser/publish/anime/{external_id}"): ("admin.parser.emergency",),
    ("POST", "/admin/parser/publish/episode"): ("admin.parser.emergency",),
    ("GET", "/admin/parser/preview/{external_id}"): ("admin.parser.settings",),
}


def permission_for(method: str, path: str) -> Permission:
    permissions = ENFORCEMENT_MATRIX[(method, path)]
    return permissions[0]


def require_enforced_permission(method: str, path: str):
    return require_permission(permission_for(method, path))
