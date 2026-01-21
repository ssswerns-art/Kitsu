from typing import Any
from fastapi import HTTPException, status

from ...models.anime import Anime
from ...models.episode import Episode
from ...models.user import User


class LockService:
    """Service for managing entity locks."""

    @staticmethod
    def check_lock(
        entity: Anime | Episode,
        fields_to_update: list[str],
        actor: User | None = None,
        has_override_permission: bool = False,
    ) -> None:
        """
        Check if entity is locked and if the update is allowed.
        Raises HTTPException if update is not allowed.
        """
        # If entity is not locked, allow update
        if not entity.is_locked:
            return

        # If no locked_fields specified, entire entity is locked
        if not entity.locked_fields:
            if has_override_permission:
                return
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Entity is locked. Reason: {entity.locked_reason or 'No reason provided'}"
            )

        # Check if any of the fields to update are locked
        locked_field_set = set(entity.locked_fields)
        fields_to_update_set = set(fields_to_update)
        
        conflicting_fields = locked_field_set.intersection(fields_to_update_set)
        
        if conflicting_fields:
            if has_override_permission:
                return
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Fields {', '.join(conflicting_fields)} are locked. Reason: {entity.locked_reason or 'No reason provided'}"
            )

    @staticmethod
    def check_parser_update(
        entity: Anime | Episode,
        fields_to_update: list[str],
        actor_type: str,
    ) -> None:
        """
        Check if parser is allowed to update the entity.
        Parser cannot update manually created or locked content.
        """
        # If this is not a parser update, allow it
        if actor_type != "system":
            return

        # Parser cannot update manual content
        if entity.source == "manual":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Parser cannot update manually created content"
            )

        # Parser cannot update locked content (even if specific fields)
        if entity.is_locked:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Parser cannot update locked content. Reason: {entity.locked_reason or 'No reason provided'}"
            )

    @staticmethod
    def serialize_entity(entity: Any) -> dict[str, Any]:
        """Serialize entity for audit logging."""
        if hasattr(entity, '__dict__'):
            data = {}
            for key, value in entity.__dict__.items():
                if key.startswith('_'):
                    continue
                # Convert UUIDs and datetimes to strings for JSON serialization
                if hasattr(value, 'isoformat'):
                    data[key] = value.isoformat()
                elif hasattr(value, '__str__') and not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                    data[key] = str(value)
                else:
                    data[key] = value
            return data
        return {}
