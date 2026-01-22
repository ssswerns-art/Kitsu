from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=settings.db_pool_pre_ping,
)
# ⚠️ WARNING: expire_on_commit=False — CONTROLLED STATE RISK
# ============================================================
# This configuration keeps ORM objects attached and VALID after session.commit().
#
# RISKS:
# • Objects retain their in-memory state after commit — NOT automatically refreshed from DB
# • Subsequent reads of the same object may return STALE DATA if DB was modified externally
# • Concurrent modifications by other sessions will NOT be reflected
# • Attributes accessed post-commit reflect PRE-COMMIT values unless explicitly refreshed
#
# MITIGATION REQUIRED:
# • ALWAYS call await session.refresh(obj) before reusing objects post-commit
# • OR execute fresh query to get current DB state
# • DO NOT rely on object attribute values being current after commit
#
# RATIONALE:
# This is a conscious performance trade-off to avoid automatic DB round-trips on every commit.
# In high-throughput scenarios, the cost of auto-expiring all objects outweighs the risk
# when proper refresh discipline is maintained.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # INTENTIONAL — see WARNING above
)


# ═══════════════════════════════════════════════════════════════════════════════
# ARCHITECTURAL CONTRACT: ORM Object Lifecycle Post-Commit
# ═══════════════════════════════════════════════════════════════════════════════
#
# RULE: CRUD layer MUST NOT assume ORM objects are fresh after session.commit()
#
# SERVICE LAYER OBLIGATIONS:
# ──────────────────────────
# When reusing ORM objects after commit, Service implementations MUST:
#
#   1. Execute fresh query:
#      result = await session.execute(select(Model).where(...))
#      obj = result.scalar_one()
#
#   2. Explicitly refresh existing object:
#      await session.refresh(obj)
#
# CRITICAL SCENARIOS:
# ───────────────────
# • Admin services modifying then reading same entity
# • Multi-step operations (create → commit → update same object)
# • Workflows returning committed objects to caller
# • Background tasks operating on stale session objects
#
# ENFORCEMENT:
# This is NOT enforced by code but is MANDATORY architectural discipline.
# Violations WILL cause silent data inconsistency bugs in production.
# Code reviews MUST verify refresh/re-query patterns in commit paths.
#
# ═══════════════════════════════════════════════════════════════════════════════

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
