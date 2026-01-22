"""Tests for Redis singleton lifecycle state safety.

This module tests that the Redis singleton implementation is safe against:
- Race conditions during initialization
- Double-close scenarios
- Using closed clients
- Concurrent access patterns
"""

import asyncio
import pytest

from app.infrastructure import redis


@pytest.mark.anyio
async def test_init_redis_is_idempotent() -> None:
    """Test that calling init_redis() multiple times is safe and returns same client."""
    # Reset state for this test
    redis._reset_for_testing()
    
    # Mock Redis URL (we'll use a fake one since we're testing lifecycle, not actual connection)
    redis_url = "redis://localhost:6379/0"
    
    # First initialization
    try:
        client1 = await redis.init_redis(redis_url)
        
        # Second initialization should return same client
        client2 = await redis.init_redis(redis_url)
        
        assert client1 is client2, "init_redis should return same client when called twice"
        assert redis._redis_state == redis._RedisLifecycleState.INITIALIZED
        
    finally:
        # Cleanup
        await redis.close_redis()


@pytest.mark.anyio
async def test_close_redis_is_idempotent() -> None:
    """Test that calling close_redis() multiple times is safe."""
    # Reset state for this test
    redis._reset_for_testing()
    
    redis_url = "redis://localhost:6379/0"
    
    try:
        await redis.init_redis(redis_url)
        
        # First close
        await redis.close_redis()
        assert redis._redis_state == redis._RedisLifecycleState.CLOSED
        assert redis._redis_client is None
        
        # Second close should be safe (no error)
        await redis.close_redis()
        assert redis._redis_state == redis._RedisLifecycleState.CLOSED
        assert redis._redis_client is None
        
    finally:
        # Ensure cleanup
        redis._reset_for_testing()


@pytest.mark.anyio
async def test_close_without_init_is_safe() -> None:
    """Test that calling close_redis() without init is safe."""
    # Reset state for this test
    redis._reset_for_testing()
    
    # Should not raise any error
    await redis.close_redis()
    assert redis._redis_state == redis._RedisLifecycleState.UNINITIALIZED
    assert redis._redis_client is None


@pytest.mark.anyio
async def test_get_redis_after_close_raises_error() -> None:
    """Test that get_redis() raises error after close_redis()."""
    # Reset state for this test
    redis._reset_for_testing()
    
    redis_url = "redis://localhost:6379/0"
    
    try:
        await redis.init_redis(redis_url)
        
        # Should work when initialized
        client = redis.get_redis()
        assert client is not None
        
        # Close
        await redis.close_redis()
        
        # Should raise error after close
        with pytest.raises(RuntimeError, match="not available.*CLOSED"):
            redis.get_redis()
            
    finally:
        # Cleanup
        redis._reset_for_testing()


@pytest.mark.anyio
async def test_get_redis_before_init_raises_error() -> None:
    """Test that get_redis() raises error before init_redis()."""
    # Reset state for this test
    redis._reset_for_testing()
    
    # Should raise error when uninitialized
    with pytest.raises(RuntimeError, match="not available.*UNINITIALIZED"):
        redis.get_redis()


@pytest.mark.anyio
async def test_reinit_after_close_is_allowed() -> None:
    """Test that init_redis() can be called again after close_redis()."""
    # Reset state for this test
    redis._reset_for_testing()
    
    redis_url = "redis://localhost:6379/0"
    
    try:
        # Initial cycle
        client1 = await redis.init_redis(redis_url)
        await redis.close_redis()
        
        # Re-initialize
        client2 = await redis.init_redis(redis_url)
        
        # Should be a new client instance
        assert client2 is not client1, "Should create new client after close"
        assert redis._redis_state == redis._RedisLifecycleState.INITIALIZED
        
        # Should work
        client = redis.get_redis()
        assert client is client2
        
    finally:
        # Cleanup
        await redis.close_redis()


@pytest.mark.anyio
async def test_concurrent_init_is_safe() -> None:
    """Test that concurrent calls to init_redis() don't create multiple clients."""
    # Reset state for this test
    redis._reset_for_testing()
    
    redis_url = "redis://localhost:6379/0"
    
    try:
        # Start multiple concurrent initializations
        tasks = [redis.init_redis(redis_url) for _ in range(10)]
        clients = await asyncio.gather(*tasks)
        
        # All should return the same client
        first_client = clients[0]
        for client in clients[1:]:
            assert client is first_client, "Concurrent init should return same client"
        
        assert redis._redis_state == redis._RedisLifecycleState.INITIALIZED
        
    finally:
        # Cleanup
        await redis.close_redis()


@pytest.mark.anyio
async def test_concurrent_close_is_safe() -> None:
    """Test that concurrent calls to close_redis() are safe."""
    # Reset state for this test
    redis._reset_for_testing()
    
    redis_url = "redis://localhost:6379/0"
    
    try:
        await redis.init_redis(redis_url)
        
        # Start multiple concurrent closes
        tasks = [redis.close_redis() for _ in range(10)]
        await asyncio.gather(*tasks)
        
        # Should be closed with no errors
        assert redis._redis_state == redis._RedisLifecycleState.CLOSED
        assert redis._redis_client is None
        
    finally:
        # Ensure cleanup
        redis._reset_for_testing()


@pytest.mark.anyio
async def test_concurrent_init_and_close() -> None:
    """Test that concurrent init and close operations don't cause race conditions."""
    # Reset state for this test
    redis._reset_for_testing()
    
    redis_url = "redis://localhost:6379/0"
    
    try:
        # Run multiple init/close cycles concurrently
        async def init_close_cycle():
            await redis.init_redis(redis_url)
            await redis.close_redis()
        
        tasks = [init_close_cycle() for _ in range(5)]
        await asyncio.gather(*tasks)
        
        # Final state should be deterministic (CLOSED or INITIALIZED)
        assert redis._redis_state in [
            redis._RedisLifecycleState.CLOSED,
            redis._RedisLifecycleState.INITIALIZED,
        ]
        
    finally:
        # Cleanup
        await redis.close_redis()


@pytest.mark.anyio
async def test_state_transitions_are_correct() -> None:
    """Test that state transitions follow the documented contract."""
    # Reset state for this test
    redis._reset_for_testing()
    
    redis_url = "redis://localhost:6379/0"
    
    try:
        # UNINITIALIZED -> INITIALIZED
        assert redis._redis_state == redis._RedisLifecycleState.UNINITIALIZED
        await redis.init_redis(redis_url)
        assert redis._redis_state == redis._RedisLifecycleState.INITIALIZED
        
        # INITIALIZED -> INITIALIZED (idempotent)
        await redis.init_redis(redis_url)
        assert redis._redis_state == redis._RedisLifecycleState.INITIALIZED
        
        # INITIALIZED -> CLOSED
        await redis.close_redis()
        assert redis._redis_state == redis._RedisLifecycleState.CLOSED
        
        # CLOSED -> CLOSED (idempotent)
        await redis.close_redis()
        assert redis._redis_state == redis._RedisLifecycleState.CLOSED
        
        # CLOSED -> INITIALIZED (restart)
        await redis.init_redis(redis_url)
        assert redis._redis_state == redis._RedisLifecycleState.INITIALIZED
        
    finally:
        # Cleanup
        await redis.close_redis()
