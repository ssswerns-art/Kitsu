"""Redis client for distributed coordination.

This module provides async Redis operations for:
- Distributed locks
- Rate limiting counters
- Job coordination

No global state is stored in memory - all coordination uses Redis.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from enum import Enum, auto
from typing import AsyncGenerator

from redis.asyncio import Redis as AsyncRedis, from_url as async_from_url
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class _RedisLifecycleState(Enum):
    """Lifecycle states for Redis singleton.
    
    State transitions:
    - UNINITIALIZED -> INITIALIZED (via init_redis)
    - INITIALIZED -> CLOSED (via close_redis)
    - CLOSED -> INITIALIZED (via init_redis - allows restart)
    
    Invariants:
    - init_redis() is idempotent: multiple calls in INITIALIZED state are no-ops
    - close_redis() is idempotent: multiple calls in CLOSED/UNINITIALIZED state are no-ops
    - get_redis() raises RuntimeError if state is not INITIALIZED
    """
    UNINITIALIZED = auto()
    INITIALIZED = auto()
    CLOSED = auto()


class RedisClient:
    """Async Redis client for distributed coordination.
    
    This client provides methods for distributed locking and coordination
    across multiple worker instances without storing any state in memory.
    """
    
    def __init__(self, redis_url: str) -> None:
        """Initialize Redis client.
        
        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0)
        """
        self._redis_url = redis_url
        self._redis: AsyncRedis | None = None
    
    async def connect(self) -> None:
        """Establish Redis connection."""
        if self._redis is None:
            self._redis = async_from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("Redis connection established")
    
    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
            logger.info("Redis connection closed")
    
    async def _ensure_connected(self) -> AsyncRedis:
        """Ensure Redis is connected and return the client."""
        if self._redis is None:
            await self.connect()
        assert self._redis is not None
        return self._redis
    
    @asynccontextmanager
    async def acquire_lock(
        self,
        key: str,
        ttl_seconds: int = 60,
        retry_interval: float = 1.0,
    ) -> AsyncGenerator[bool, None]:
        """Acquire a distributed lock using Redis SET NX EX.
        
        This implements a simple distributed lock that automatically expires.
        Only one worker can hold the lock at a time.
        
        Args:
            key: Lock key
            ttl_seconds: Lock TTL (auto-release on crash)
            retry_interval: How long to wait before retrying (not used for non-blocking)
        
        Yields:
            True if lock was acquired, False otherwise
        """
        redis = await self._ensure_connected()
        lock_key = f"lock:{key}"
        
        try:
            # Try to acquire lock (non-blocking)
            # SET key value NX EX ttl
            acquired = await redis.set(lock_key, "1", nx=True, ex=ttl_seconds)
            yield bool(acquired)
        finally:
            # Release lock if we acquired it
            if acquired:
                try:
                    await redis.delete(lock_key)
                except RedisError:
                    # Lock will auto-expire anyway
                    pass
    
    async def try_acquire_lock(self, key: str, ttl_seconds: int = 60) -> bool:
        """Try to acquire a lock without blocking.
        
        Args:
            key: Lock key
            ttl_seconds: Lock TTL (auto-release on crash)
            
        Returns:
            True if lock was acquired, False otherwise
        """
        redis = await self._ensure_connected()
        lock_key = f"lock:{key}"
        acquired = await redis.set(lock_key, "1", nx=True, ex=ttl_seconds)
        return bool(acquired)
    
    async def release_lock(self, key: str) -> None:
        """Release a lock.
        
        Args:
            key: Lock key
        """
        redis = await self._ensure_connected()
        lock_key = f"lock:{key}"
        await redis.delete(lock_key)
    
    async def extend_lock(self, key: str, ttl_seconds: int = 60) -> bool:
        """Extend the TTL of an existing lock.
        
        Args:
            key: Lock key
            ttl_seconds: New TTL
            
        Returns:
            True if lock exists and was extended, False otherwise
        """
        redis = await self._ensure_connected()
        lock_key = f"lock:{key}"
        result = await redis.expire(lock_key, ttl_seconds)
        return bool(result)
    
    async def increment_counter(
        self,
        key: str,
        ttl_seconds: int | None = None,
    ) -> int:
        """Increment a counter and optionally set TTL.
        
        Used for rate limiting - increments counter and sets expiry.
        
        Args:
            key: Counter key
            ttl_seconds: TTL for the counter (set only on first increment)
            
        Returns:
            New counter value
        """
        redis = await self._ensure_connected()
        
        # Use pipeline for atomic operations
        async with redis.pipeline(transaction=True) as pipe:
            # Increment counter
            pipe.incr(key)
            
            # Set TTL only if this is the first increment
            # (EXPIRE returns 0 if key doesn't exist after INCR, but we just created it)
            if ttl_seconds is not None:
                # Use NX flag to only set expiry if not already set
                # This is a pipeline, so we need to check existence first
                pipe.expire(key, ttl_seconds, nx=True)
            
            results = await pipe.execute()
            return int(results[0])
    
    async def get_counter(self, key: str) -> int:
        """Get current counter value.
        
        Args:
            key: Counter key
            
        Returns:
            Counter value (0 if not exists)
        """
        redis = await self._ensure_connected()
        value = await redis.get(key)
        return int(value) if value else 0
    
    async def delete_counter(self, key: str) -> None:
        """Delete a counter.
        
        Args:
            key: Counter key
        """
        redis = await self._ensure_connected()
        await redis.delete(key)
    
    async def set_value(
        self,
        key: str,
        value: str,
        ttl_seconds: int | None = None,
    ) -> None:
        """Set a string value with optional TTL.
        
        Args:
            key: Key
            value: Value
            ttl_seconds: Optional TTL
        """
        redis = await self._ensure_connected()
        if ttl_seconds:
            await redis.setex(key, ttl_seconds, value)
        else:
            await redis.set(key, value)
    
    async def get_value(self, key: str) -> str | None:
        """Get a string value.
        
        Args:
            key: Key
            
        Returns:
            Value or None if not exists
        """
        redis = await self._ensure_connected()
        return await redis.get(key)
    
    async def delete_value(self, key: str) -> None:
        """Delete a value.
        
        Args:
            key: Key
        """
        redis = await self._ensure_connected()
        await redis.delete(key)
    
    async def check_job_running(self, job_id: str, ttl_seconds: int = 300) -> bool:
        """Check if a job is already running and mark it if not.
        
        This is used for job deduplication across workers.
        
        Args:
            job_id: Unique job identifier
            ttl_seconds: How long the job is expected to run (max)
            
        Returns:
            True if job is now running (caller should proceed),
            False if job was already running (caller should skip)
        """
        redis = await self._ensure_connected()
        job_key = f"job:running:{job_id}"
        
        # Try to set the job marker with NX (only if not exists)
        acquired = await redis.set(job_key, "1", nx=True, ex=ttl_seconds)
        return bool(acquired)
    
    async def mark_job_complete(self, job_id: str) -> None:
        """Mark a job as complete (remove running marker).
        
        Args:
            job_id: Unique job identifier
        """
        redis = await self._ensure_connected()
        job_key = f"job:running:{job_id}"
        await redis.delete(job_key)


# Global instance (created at startup, not at import)
# Protected by _redis_lock to prevent race conditions during initialization/shutdown
_redis_client: RedisClient | None = None
_redis_state: _RedisLifecycleState = _RedisLifecycleState.UNINITIALIZED
_redis_lock: asyncio.Lock = asyncio.Lock()


async def init_redis(redis_url: str) -> RedisClient:
    """Initialize global Redis client.
    
    This function is idempotent - calling it multiple times when already
    initialized will return the existing client without creating a new one.
    
    Thread-safety: Protected by asyncio.Lock to prevent race conditions.
    
    State transitions:
    - UNINITIALIZED -> INITIALIZED: Creates new client and connects
    - INITIALIZED -> INITIALIZED: Returns existing client (no-op)
    - CLOSED -> INITIALIZED: Creates new client and connects (allows restart)
    
    Args:
        redis_url: Redis connection URL
        
    Returns:
        Redis client instance
    """
    global _redis_client, _redis_state
    
    async with _redis_lock:
        # Idempotent: if already initialized, return existing client
        if _redis_state == _RedisLifecycleState.INITIALIZED:
            assert _redis_client is not None
            logger.debug("Redis already initialized, returning existing client")
            return _redis_client
        
        # Create new client (handles UNINITIALIZED and CLOSED states)
        logger.info(f"Initializing Redis client (current state: {_redis_state.name})")
        _redis_client = RedisClient(redis_url)
        await _redis_client.connect()
        _redis_state = _RedisLifecycleState.INITIALIZED
        logger.info("Redis client initialized successfully")
        return _redis_client


async def close_redis() -> None:
    """Close global Redis client.
    
    This function is idempotent - calling it multiple times or when not
    initialized will safely do nothing.
    
    Thread-safety: Protected by asyncio.Lock to prevent race conditions.
    
    State transitions:
    - INITIALIZED -> CLOSED: Disconnects and cleans up client
    - CLOSED -> CLOSED: No-op
    - UNINITIALIZED -> UNINITIALIZED: No-op
    """
    global _redis_client, _redis_state
    
    async with _redis_lock:
        # Idempotent: if not initialized, nothing to close
        if _redis_state != _RedisLifecycleState.INITIALIZED:
            logger.debug(f"Redis not initialized (state: {_redis_state.name}), nothing to close")
            return
        
        # Close the client
        logger.info("Closing Redis client")
        if _redis_client is not None:
            await _redis_client.disconnect()
            _redis_client = None
        _redis_state = _RedisLifecycleState.CLOSED
        logger.info("Redis client closed successfully")


def get_redis() -> RedisClient:
    """Get the global async Redis client.
    
    Returns:
        Redis client instance
        
    Raises:
        RuntimeError: If Redis client not initialized
    """
    # CONTRACT: get_redis() MUST NOT be called before init_redis()
    if _redis_state != _RedisLifecycleState.INITIALIZED or _redis_client is None:
        raise RuntimeError("Redis client not initialized. Call init_redis() first.")
    return _redis_client
