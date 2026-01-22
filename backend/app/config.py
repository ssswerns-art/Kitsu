import json
import os
import threading
from urllib.parse import urlparse

from dotenv import load_dotenv
from pydantic import BaseModel, Field


load_dotenv()


class Settings(BaseModel):
    app_name: str = Field(default="Kitsu Backend")
    debug: bool = Field(default=False)
    database_url: str = Field(default="")
    redis_url: str = Field(default="redis://localhost:6379/0")
    allowed_origins: list[str] = Field(default_factory=list)
    db_pool_size: int = Field(default=5)
    db_max_overflow: int = Field(default=10)
    db_pool_recycle: int = Field(default=1800)
    db_pool_pre_ping: bool = Field(default=True)
    secret_key: str | None = Field(default=None)
    access_token_expire_minutes: int = Field(default=30)
    refresh_token_expire_days: int = Field(default=14)
    algorithm: str = Field(default="HS256")

    @classmethod
    def from_env(cls) -> "Settings":
        secret_key = os.getenv("SECRET_KEY", "").strip()
        if not secret_key:
            raise ValueError("SECRET_KEY environment variable must be set")

        raw_allowed_origins = os.getenv("ALLOWED_ORIGINS", "").strip()
        if not raw_allowed_origins:
            raise ValueError("ALLOWED_ORIGINS environment variable must be set")

        # Support both CSV format and JSON array format
        allowed_origins: list[str] = []
        if raw_allowed_origins.startswith("["):
            # JSON array format: ["http://localhost:3000", "http://localhost:8080"]
            try:
                parsed_list = json.loads(raw_allowed_origins)
                if not isinstance(parsed_list, list):
                    raise ValueError("ALLOWED_ORIGINS JSON must be an array")
                allowed_origins = [
                    origin.strip() for origin in parsed_list if isinstance(origin, str) and origin.strip()
                ]
            except json.JSONDecodeError as exc:
                raise ValueError(f"ALLOWED_ORIGINS JSON is malformed: {exc}") from exc
        else:
            # CSV format: http://localhost:3000,http://localhost:8080
            allowed_origins = [
                origin.strip() for origin in raw_allowed_origins.split(",") if origin.strip()
            ]
        
        if not allowed_origins:
            raise ValueError("ALLOWED_ORIGINS must contain at least one origin")

        if "*" in allowed_origins:
            raise ValueError(
                "ALLOWED_ORIGINS cannot contain '*' when credentialed requests are used"
            )

        for origin in allowed_origins:
            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(
                    "ALLOWED_ORIGINS must contain valid http/https origins with host"
                )

        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            raise ValueError("DATABASE_URL environment variable must be set")

        parsed_db = urlparse(database_url)
        if parsed_db.scheme != "postgresql+asyncpg":
            raise ValueError("DATABASE_URL must start with 'postgresql+asyncpg://'")
        if not parsed_db.hostname:
            raise ValueError("DATABASE_URL must include hostname")

        db_pool_size = int(os.getenv("DB_POOL_SIZE", cls.model_fields["db_pool_size"].default))
        if db_pool_size <= 0:
            raise ValueError("DB_POOL_SIZE must be greater than 0")

        db_max_overflow = int(
            os.getenv("DB_MAX_OVERFLOW", cls.model_fields["db_max_overflow"].default)
        )
        if db_max_overflow < 0:
            raise ValueError("DB_MAX_OVERFLOW must be greater than or equal to 0")

        db_pool_recycle = int(
            os.getenv("DB_POOL_RECYCLE", cls.model_fields["db_pool_recycle"].default)
        )
        if db_pool_recycle <= 0:
            raise ValueError("DB_POOL_RECYCLE must be greater than 0")

        raw_db_pool_pre_ping = os.getenv(
            "DB_POOL_PRE_PING", str(cls.model_fields["db_pool_pre_ping"].default)
        ).strip().lower()
        if raw_db_pool_pre_ping in {"1", "true", "yes", "on"}:
            db_pool_pre_ping = True
        elif raw_db_pool_pre_ping in {"0", "false", "no", "off"}:
            db_pool_pre_ping = False
        else:
            raise ValueError("DB_POOL_PRE_PING must be a boolean value")

        redis_url = os.getenv("REDIS_URL", cls.model_fields["redis_url"].default).strip()
        
        return cls(
            app_name=os.getenv("APP_NAME", cls.model_fields["app_name"].default),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            database_url=database_url,
            redis_url=redis_url,
            allowed_origins=allowed_origins,
            secret_key=secret_key,
            access_token_expire_minutes=int(
                os.getenv(
                    "ACCESS_TOKEN_EXPIRE_MINUTES",
                    cls.model_fields["access_token_expire_minutes"].default,
                )
            ),
            refresh_token_expire_days=int(
                os.getenv(
                    "REFRESH_TOKEN_EXPIRE_DAYS",
                    cls.model_fields["refresh_token_expire_days"].default,
                )
            ),
            algorithm=os.getenv("ALGORITHM", cls.model_fields["algorithm"].default),
            db_pool_size=db_pool_size,
            db_max_overflow=db_max_overflow,
            db_pool_recycle=db_pool_recycle,
            db_pool_pre_ping=db_pool_pre_ping,
        )


# Deferred settings initialization to avoid import-time side effects (ISSUE #6)
# Settings validation will happen during application startup, not module import
# ISSUE #7 FIX: Use threading.Lock for proper synchronization in both sync and async contexts
_settings_instance: Settings | None = None
_settings_lock = threading.Lock()


def get_settings() -> Settings:
    """Get settings instance, creating it on first access.
    
    This allows the module to be imported without environment validation.
    Settings validation happens when first accessed (typically during startup).
    
    ISSUE #7 FIX: Uses double-checked locking pattern with threading.Lock to prevent
    race conditions when multiple tasks/threads try to initialize settings concurrently.
    threading.Lock works correctly in both sync and async contexts.
    
    Returns:
        Settings instance
        
    Raises:
        ValueError: If required environment variables are missing or invalid
    """
    global _settings_instance
    
    # Fast path: already initialized (no lock needed)
    if _settings_instance is not None:
        return _settings_instance
    
    # Slow path: need to initialize with proper locking
    with _settings_lock:
        # Double-check: another thread might have initialized while we waited for lock
        if _settings_instance is None:
            _settings_instance = Settings.from_env()
    
    return _settings_instance


# Create settings proxy for backward compatibility
# Actual Settings.from_env() is deferred until first attribute access
class _SettingsProxy:
    """Proxy to defer settings creation until first attribute access."""
    
    def __getattr__(self, name: str):
        return getattr(get_settings(), name)


settings = _SettingsProxy()  # type: ignore[assignment]
