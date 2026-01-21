"""Declarative mapping of protected endpoints to required permissions.

DEPRECATED: This matrix is now largely unused.

Admin endpoints now use PermissionService directly via dependency injection.
This file is kept only for potential non-admin middleware-based routes.

Per SECURITY-01 contract:
- All permissions must be explicit (no wildcards)
- Only allowed permissions from rbac_contract.py are valid
- Admin endpoints do NOT use this matrix

TODO REFACTOR-03: Remove this file entirely if no middleware routes remain.
"""
from ..auth.rbac_contract import ALLOWED_PERMISSIONS

Permission = str

# This matrix is now EMPTY because all admin endpoints use PermissionService directly
# If you need to add a middleware-protected route, use the pattern:
#   ("METHOD", "/path"): ("permission.name",)
# where permission.name is from ALLOWED_PERMISSIONS
ENFORCEMENT_MATRIX: dict[tuple[str, str], tuple[Permission, ...]] = {
    # All admin endpoints migrated to PermissionService dependency injection
    # Example (if needed): ("GET", "/api/public/data"): ("content.read",)
}
