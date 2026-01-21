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


class GlobalJobCounter:
    """
    Cluster-wide atomic counter for job concurrency limits.
    Implements backpressure by enforcing max concurrent jobs.
    """

    def __init__(self, redis_client: AsyncRedis, counter_key: str, max_value: int):
        """
        Args:
            redis_client: Async Redis client
            counter_key: Unique key for this counter
            max_value: Maximum allowed concurrent jobs
        """
        self._redis = redis_client
        self._counter_key = f"counter:{counter_key}"
        self._max_value = max_value

    async def try_acquire(self) -> bool:
        """
        Attempt to acquire a job slot.
        Returns True if acquired (counter incremented), False if limit reached or error.
        """
        try:
            # Atomically increment only if current value < max_value
            current = await self._redis.get(self._counter_key)
            current_val = int(current) if current else 0
            
            if current_val >= self._max_value:
                logger.debug(
                    "Counter limit reached counter=%s current=%d max=%d",
                    self._counter_key,
                    current_val,
                    self._max_value,
                )
                return False
            
            # Increment counter
            new_val = await self._redis.incr(self._counter_key)
            
            # Double-check we didn't exceed limit due to race condition
            if new_val > self._max_value:
                # Rollback increment
                await self._redis.decr(self._counter_key)
                logger.debug(
                    "Counter limit exceeded after increment counter=%s value=%d max=%d",
                    self._counter_key,
                    new_val,
                    self._max_value,
                )
                return False
            
            logger.debug(
                "Counter acquired counter=%s value=%d max=%d",
                self._counter_key,
                new_val,
                self._max_value,
            )
            return True
            
        except RedisError as exc:
            logger.error(
                "Redis operation failed operation=INCR key=%s error=%s",
                self._counter_key,
                exc,
            )
            return False

    async def release(self) -> bool:
        """
        Release a job slot by decrementing the counter.
        Returns True if released, False on error.
        """
        try:
            current = await self._redis.get(self._counter_key)
            current_val = int(current) if current else 0
            
            if current_val <= 0:
                logger.warning(
                    "Counter already at zero counter=%s",
                    self._counter_key,
                )
                return True
            
            new_val = await self._redis.decr(self._counter_key)
            logger.debug(
                "Counter released counter=%s value=%d",
                self._counter_key,
                new_val,
            )
            return True
            
        except RedisError as exc:
            logger.error(
                "Redis operation failed operation=DECR key=%s error=%s",
                self._counter_key,
                exc,
            )
            return False

    async def get_current(self) -> int:
        """Get current counter value."""
        try:
            current = await self._redis.get(self._counter_key)
            return int(current) if current else 0
        except RedisError as exc:
            logger.error(
                "Redis operation failed operation=GET key=%s error=%s",
                self._counter_key,
                exc,
            )
            return 0
