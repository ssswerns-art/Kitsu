import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.permission import Permission
from ..models.role_permission import RolePermission


class PermissionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, name: str, display_name: str, resource: str, action: str, description: str | None = None, is_system: bool = False) -> Permission:
        permission = Permission(
            name=name,
            display_name=display_name,
            resource=resource,
            action=action,
            description=description,
            is_system=is_system,
        )
        self.session.add(permission)
        await self.session.commit()
        await self.session.refresh(permission)
        return permission

    async def get_by_id(self, permission_id: uuid.UUID) -> Permission | None:
        return await self.session.get(Permission, permission_id)

    async def get_by_name(self, name: str) -> Permission | None:
        result = await self.session.execute(
            select(Permission).where(Permission.name == name)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Permission]:
        result = await self.session.execute(select(Permission))
        return list(result.scalars().all())

    async def list_by_resource(self, resource: str) -> list[Permission]:
        result = await self.session.execute(
            select(Permission).where(Permission.resource == resource)
        )
        return list(result.scalars().all())

    async def get_role_permissions(self, role_id: uuid.UUID) -> list[Permission]:
        result = await self.session.execute(
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
        )
        return list(result.scalars().all())

    async def get_user_permissions(self, user_id: uuid.UUID) -> list[Permission]:
        from ..models.user_role import UserRole
        from ..models.role import Role
        
        result = await self.session.execute(
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .where(Role.is_active)
            .distinct()
        )
        return list(result.scalars().all())
