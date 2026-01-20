import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from ...crud.permission import PermissionRepository
from ...models.user import User


class PermissionService:
    """Service for checking user permissions."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.permission_repo = PermissionRepository(session)

    async def has_permission(self, user: User | None, permission_name: str) -> bool:
        """Check if a user has a specific permission."""
        if user is None:
            return False
        
        # Get all user permissions
        permissions = await self.permission_repo.get_user_permissions(user.id)
        
        # Check if the user has the exact permission
        for perm in permissions:
            if perm.name == permission_name:
                return True
        
        return False

    async def has_any_permission(self, user: User | None, permission_names: list[str]) -> bool:
        """Check if a user has any of the specified permissions."""
        if user is None:
            return False
        
        permissions = await self.permission_repo.get_user_permissions(user.id)
        permission_set = {perm.name for perm in permissions}
        
        return any(perm_name in permission_set for perm_name in permission_names)

    async def has_all_permissions(self, user: User | None, permission_names: list[str]) -> bool:
        """Check if a user has all of the specified permissions."""
        if user is None:
            return False
        
        permissions = await self.permission_repo.get_user_permissions(user.id)
        permission_set = {perm.name for perm in permissions}
        
        return all(perm_name in permission_set for perm_name in permission_names)

    async def get_user_permissions(self, user_id: uuid.UUID) -> list[str]:
        """Get all permission names for a user."""
        permissions = await self.permission_repo.get_user_permissions(user_id)
        return [perm.name for perm in permissions]

    async def require_permission(self, user: User | None, permission_name: str) -> None:
        """Raise an exception if the user doesn't have the required permission."""
        if not await self.has_permission(user, permission_name):
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission_name} required"
            )
