import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from ...crud.permission import PermissionRepository
from ...models.user import User
from ...auth import rbac_contract
from ...database import AsyncSessionLocal


class PermissionService:
    """Service for checking user permissions with hard invariant enforcement.
    
    SECURITY: This is the ONLY authorized way to check permissions.
    All permission checks MUST go through this service.
    
    Per SECURITY-01 contract, this service enforces:
    - No wildcard permissions
    - Parser ≠ Admin invariant
    - System ≠ User invariant
    - No implicit permissions from roles
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.permission_repo = PermissionRepository(session)

    async def has_permission(
        self, 
        user: User | None, 
        permission_name: str,
        actor_type: str = "user"
    ) -> bool:
        """Check if a user has a specific permission with hard invariant enforcement.
        
        SECURITY: This enforces all RBAC contract invariants.
        
        Args:
            user: The user to check permissions for
            permission_name: The permission to check (must be explicit, no wildcards)
            actor_type: The type of actor ('user', 'system', 'anonymous')
            
        Returns:
            bool: True if the user has the permission, False otherwise
            
        Raises:
            ValueError: If permission contains wildcards or actor_type is invalid
            PermissionError: If hard invariants are violated
        """
        # SECURITY: Validate actor_type
        rbac_contract.validate_actor_type(actor_type)
        
        # SECURITY: Validate permission (no wildcards)
        try:
            rbac_contract.validate_permission(permission_name)
        except ValueError:
            # Permission not in contract or contains wildcards
            return False
        
        # SECURITY: Enforce hard invariant - System actors cannot use admin permissions
        try:
            rbac_contract.check_system_cannot_use_admin_permissions(
                actor_type, permission_name
            )
        except PermissionError:
            # Hard invariant violation - system trying to use admin permission
            return False
        
        # Anonymous users have no permissions
        if actor_type == rbac_contract.ActorType.ANONYMOUS or user is None:
            return False
        
        # Get all user permissions from database
        permissions = await self.permission_repo.get_user_permissions(user.id)
        
        # Check if the user has the exact permission (no wildcards, no fuzzy matching)
        for perm in permissions:
            if perm.name == permission_name:
                # SECURITY: No implicit permissions - only explicit permission grants
                return rbac_contract.check_no_implicit_permissions(
                    has_role=True,  # Ignored by the check
                    has_explicit_permission=True
                )
        
        return False

    async def has_any_permission(
        self, 
        user: User | None, 
        permission_names: list[str],
        actor_type: str = "user"
    ) -> bool:
        """Check if a user has any of the specified permissions.
        
        Args:
            user: The user to check permissions for
            permission_names: List of permissions to check
            actor_type: The type of actor ('user', 'system', 'anonymous')
            
        Returns:
            bool: True if the user has any of the permissions
        """
        if user is None or actor_type == rbac_contract.ActorType.ANONYMOUS:
            return False
        
        for perm_name in permission_names:
            if await self.has_permission(user, perm_name, actor_type):
                return True
        
        return False

    async def has_all_permissions(
        self, 
        user: User | None, 
        permission_names: list[str],
        actor_type: str = "user"
    ) -> bool:
        """Check if a user has all of the specified permissions.
        
        Args:
            user: The user to check permissions for
            permission_names: List of permissions to check
            actor_type: The type of actor ('user', 'system', 'anonymous')
            
        Returns:
            bool: True if the user has all of the permissions
        """
        if user is None or actor_type == rbac_contract.ActorType.ANONYMOUS:
            return False
        
        for perm_name in permission_names:
            if not await self.has_permission(user, perm_name, actor_type):
                return False
        
        return True

    async def get_user_permissions(self, user_id: uuid.UUID) -> list[str]:
        """Get all permission names for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            list[str]: List of permission names
        """
        permissions = await self.permission_repo.get_user_permissions(user_id)
        return [perm.name for perm in permissions]

    async def require_permission(
        self, 
        user: User | None, 
        permission_name: str,
        actor_type: str = "user"
    ) -> None:
        """Raise an exception if the user doesn't have the required permission.
        
        SECURITY: This is the enforcement point for permission checks.
        All 403 errors are generated here and logged to audit.
        
        Args:
            user: The user to check permissions for
            permission_name: The permission required
            actor_type: The type of actor ('user', 'system', 'anonymous')
            
        Raises:
            HTTPException: 403 Forbidden if permission is denied
        """
        if not await self.has_permission(user, permission_name, actor_type):
            # SECURITY: Log permission denial to audit in ISOLATED transaction
            # Use a separate session to prevent commit leakage to main transaction
            # Import here to avoid circular dependency
            from ...services.audit.audit_service import AuditService
            try:
                async with AsyncSessionLocal() as audit_session:
                    audit_service = AuditService(audit_session)
                    await audit_service.log_permission_denied(
                        permission=permission_name,
                        actor=user,
                        actor_type=actor_type
                    )
                    await audit_session.commit()
            except Exception:
                # Don't fail the permission check if audit logging fails
                # (logging failures shouldn't bypass security)
                pass
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission_name} required"
            )
