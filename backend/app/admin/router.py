"""
Centralized Admin Router (SKELETON ONLY).

This module is a placeholder for future admin endpoints.
Currently contains no endpoints - this is by design for Phase 3.

Future phases will add admin infrastructure endpoints with RBAC protection.

NOTE: No active endpoints in this phase. Empty router skeleton only.
"""
from __future__ import annotations

from fastapi import APIRouter

# Create empty admin router (no endpoints in Phase 3)
router = APIRouter(
    prefix="/admin",
    tags=["admin-core"],
)

# TODO: Future phases will add endpoints:
# - /admin/health - Admin access verification
# - /admin/permissions/my - Current user's permissions
# - /admin/permissions/role/{role} - Role permission lookup
#
# Phase 3 (current): Empty router - no endpoints
# Phase 4 (future): Active admin endpoints with RBAC protection
