import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.role import Role
from ..models.user_role import UserRole
from ..models.role_permission import RolePermission


class RoleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, name: str, display_name: str, description: str | None = None, is_system: bool = False) -> Role:
        role = Role(
            name=name,
            display_name=display_name,
            description=description,
            is_system=is_system,
        )
        self.session.add(role)
        await self.session.flush()
        await self.session.refresh(role)
        return role

    async def get_by_id(self, role_id: uuid.UUID) -> Role | None:
        return await self.session.get(Role, role_id)

    async def get_by_name(self, name: str) -> Role | None:
        result = await self.session.execute(
            select(Role).where(Role.name == name)
        )
        return result.scalar_one_or_none()

    async def list_all(self, include_inactive: bool = False) -> list[Role]:
        query = select(Role)
        if not include_inactive:
            query = query.where(Role.is_active)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(self, role: Role) -> Role:
        await self.session.flush()
        await self.session.refresh(role)
        return role

    async def assign_permission(self, role_id: uuid.UUID, permission_id: uuid.UUID) -> RolePermission:
        role_permission = RolePermission(role_id=role_id, permission_id=permission_id)
        self.session.add(role_permission)
        await self.session.flush()
        await self.session.refresh(role_permission)
        return role_permission

    async def remove_permission(self, role_id: uuid.UUID, permission_id: uuid.UUID) -> None:
        result = await self.session.execute(
            select(RolePermission).where(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == permission_id
            )
        )
        role_permission = result.scalar_one_or_none()
        if role_permission:
            await self.session.delete(role_permission)
            await self.session.flush()

    async def assign_to_user(self, user_id: uuid.UUID, role_id: uuid.UUID, granted_by: uuid.UUID | None = None) -> UserRole:
        user_role = UserRole(user_id=user_id, role_id=role_id, granted_by=granted_by)
        self.session.add(user_role)
        await self.session.flush()
        await self.session.refresh(user_role)
        return user_role

    async def remove_from_user(self, user_id: uuid.UUID, role_id: uuid.UUID) -> None:
        result = await self.session.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id
            )
        )
        user_role = result.scalar_one_or_none()
        if user_role:
            await self.session.delete(user_role)
            await self.session.flush()

    async def get_user_roles(self, user_id: uuid.UUID) -> list[Role]:
        result = await self.session.execute(
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .where(Role.is_active)
        )
        return list(result.scalars().all())
