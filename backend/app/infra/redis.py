import os
import logging
from typing import Any
from redis import Redis, RedisError
from redis.asyncio import Redis as AsyncRedis

logger = logging.getLogger("kitsu.redis")


def get_redis_client() -> Redis:
    """Create a synchronous Redis client from environment variable."""
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise ValueError("REDIS_URL environment variable must be set")
    return Redis.from_url(redis_url, decode_responses=True)


def get_async_redis_client() -> AsyncRedis:
    """Create an async Redis client from environment variable."""
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise ValueError("REDIS_URL environment variable must be set")
    return AsyncRedis.from_url(redis_url, decode_responses=True)


class DistributedLock:
    """
    Distributed lock using Redis SET NX EX.
    Ensures only one instance across multiple workers can hold the lock.
    """

    def __init__(self, redis_client: AsyncRedis, lock_key: str, ttl_seconds: int = 30):
        """
        Args:
            redis_client: Async Redis client
            lock_key: Unique key for this lock
            ttl_seconds: Lock TTL (auto-release on crash)
        """
        self._redis = redis_client
        self._lock_key = f"lock:{lock_key}"
        self._ttl = ttl_seconds
        self._acquired = False

    async def acquire(self) -> bool:
        """
        Attempt to acquire the lock.
        Returns True if acquired, False otherwise.
        """
        try:
            # SET NX EX: set if not exists with expiration
            result = await self._redis.set(
                self._lock_key, "1", nx=True, ex=self._ttl
            )
            self._acquired = bool(result)
            if self._acquired:
                logger.debug("Acquired lock: %s (TTL=%ds)", self._lock_key, self._ttl)
            return self._acquired
        except RedisError as exc:
            logger.error(
                "Redis operation failed operation=SET key=%s error=%s",
                self._lock_key,
                exc,
            )
            return False

    async def release(self) -> bool:
        """
        Release the lock.
        Returns True if released, False otherwise.
        """
        if not self._acquired:
            return False
        try:
            deleted = await self._redis.delete(self._lock_key)
            if deleted:
                logger.debug("Released lock: %s", self._lock_key)
                self._acquired = False
            return bool(deleted)
        except RedisError as exc:
            logger.error(
                "Redis operation failed operation=DEL key=%s error=%s",
                self._lock_key,
                exc,
            )
            return False

    async def extend(self) -> bool:
        """
        Extend lock TTL to prevent expiration.
        Returns True if extended, False otherwise.
        """
        if not self._acquired:
            return False
        try:
            # Reset TTL if key exists
            result = await self._redis.expire(self._lock_key, self._ttl)
            if result:
                logger.debug("Extended lock: %s (TTL=%ds)", self._lock_key, self._ttl)
            return bool(result)
        except RedisError as exc:
            logger.error(
                "Redis operation failed operation=EXPIRE key=%s error=%s",
                self._lock_key,
                exc,
            )
            return False
