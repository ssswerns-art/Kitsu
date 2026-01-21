import uuid

from ...domain.ports.token import RefreshTokenPort
from ...errors import AppError
from ...utils.security import hash_refresh_token


async def logout_user(
    token_port: RefreshTokenPort,
    refresh_token: str | None,
    *,
    user_id: uuid.UUID | None = None,
) -> None:
    token_hash = hash_refresh_token(refresh_token) if refresh_token else None
    try:
        stored_token = None
        if token_hash:
            stored_token = await token_port.get_by_hash(token_hash, for_update=True)

        if stored_token is None and user_id is None:
            return

        revoke_user_id = stored_token.user_id if stored_token else user_id
        if revoke_user_id is None:
            return

        await token_port.revoke(revoke_user_id)
        await token_port.commit()
    except AppError:
        await token_port.rollback()
        raise
    except Exception:
        await token_port.rollback()
        raise
