"""
DEPRECATED AND UNUSED: This module has been completely phased out.

This file is kept ONLY for reference and will be removed in REFACTOR-03.
DO NOT USE. DO NOT IMPORT. DO NOT EXTEND.

For permission checks, use ONLY:
- app.services.admin.permission_service.PermissionService dependency injection
- rbac_contract.py for permission definitions

SECURITY WARNING: This module contains legacy helpers with security risks.
Any usage of this module is a SECURITY VIOLATION.

REFACTOR-02 STATUS: ✅ ALL USAGE ELIMINATED
- Parser admin router migrated to PermissionService
- All admin endpoints use PermissionService
- No production code uses these helpers

TODO REFACTOR-03: Delete this file entirely
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

# Legacy imports kept for reference only - DO NOT USE
# from . import rbac
# from ..dependencies import get_current_role
# from ..errors import PermissionError

logger = logging.getLogger("kitsu.rbac")

if TYPE_CHECKING:
    from fastapi import Request
    OptionalRequest = Request | None
else:
    OptionalRequest = object


# All functions below are DEPRECATED and UNUSED
# They are kept only for reference and will be removed in REFACTOR-03

# def _log_deny(request: OptionalRequest, role: str, required: tuple[str, ...]) -> None:
#     """DEPRECATED - Do not use"""
#     pass

# def require_permission(permission: str):
#     """DEPRECATED - Use PermissionService.require_permission() instead"""
#     raise NotImplementedError("DEPRECATED: Use PermissionService.require_permission()")

# def require_any_permission(permissions: tuple[str, ...]):
#     """DEPRECATED - Use PermissionService.has_any_permission() instead"""
#     raise NotImplementedError("DEPRECATED: Use PermissionService.has_any_permission()")
