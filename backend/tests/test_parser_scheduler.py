"""Tests for parser scheduler.

Tests verify that the scheduler correctly determines when tasks should run
based on database configuration and last sync times.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.parser.config import ParserSettings
from app.parser.scheduler import ParserScheduler


@pytest.fixture
def settings():
    """Create default parser settings."""
    return ParserSettings(
        mode="auto",
        enable_autoupdate=True,
        update_interval_minutes=60,
    )


@pytest.fixture
def scheduler(settings):
    """Create scheduler with default settings."""
    return ParserScheduler(settings)


def test_should_run_catalog_sync_never_synced(scheduler):
    """Test catalog sync should run if never synced."""
    source = {
        "id": 1,
        "code": "shikimori",
        "enabled": True,
        "last_synced_at": None,
    }
    
    assert scheduler.should_run_catalog_sync(source) is True


def test_should_run_catalog_sync_interval_elapsed(scheduler):
    """Test catalog sync should run if interval has elapsed."""
    now = datetime.now(timezone.utc)
    last_synced = now - timedelta(hours=25)  # More than 24 hours ago
    
    source = {
        "id": 1,
        "code": "shikimori",
        "enabled": True,
        "last_synced_at": last_synced,
    }
    
    assert scheduler.should_run_catalog_sync(source, now) is True


def test_should_not_run_catalog_sync_too_recent(scheduler):
    """Test catalog sync should not run if synced recently."""
    now = datetime.now(timezone.utc)
    last_synced = now - timedelta(hours=1)  # Only 1 hour ago
    
    source = {
        "id": 1,
        "code": "shikimori",
        "enabled": True,
        "last_synced_at": last_synced,
    }
    
    assert scheduler.should_run_catalog_sync(source, now) is False


def test_should_run_catalog_sync_with_string_datetime(scheduler):
    """Test catalog sync works with ISO datetime strings."""
    now = datetime.now(timezone.utc)
    last_synced = (now - timedelta(hours=25)).isoformat()
    
    source = {
        "id": 1,
        "code": "shikimori",
        "enabled": True,
        "last_synced_at": last_synced,
    }
    
    assert scheduler.should_run_catalog_sync(source, now) is True


def test_should_run_episode_sync_when_enabled(settings):
    """Test episode sync should run when autoupdate is enabled."""
    settings.enable_autoupdate = True
    scheduler = ParserScheduler(settings)
    
    assert scheduler.should_run_episode_sync() is True


def test_should_not_run_episode_sync_when_disabled(settings):
    """Test episode sync should not run when autoupdate is disabled."""
    settings.enable_autoupdate = False
    scheduler = ParserScheduler(settings)
    
    assert scheduler.should_run_episode_sync() is False


def test_catalog_sync_interval_bounds(scheduler):
    """Test catalog sync interval respects min/max bounds."""
    interval = scheduler._get_catalog_sync_interval_minutes()
    
    # Should be within bounds
    assert interval >= 60  # MIN_CATALOG_SYNC_INTERVAL_MINUTES
    assert interval <= 60 * 24 * 7  # MAX_CATALOG_SYNC_INTERVAL_MINUTES


def test_should_run_catalog_sync_at_exact_boundary(scheduler):
    """Test catalog sync runs exactly at the interval boundary."""
    now = datetime.now(timezone.utc)
    interval_minutes = scheduler._get_catalog_sync_interval_minutes()
    last_synced = now - timedelta(minutes=interval_minutes)
    
    source = {
        "id": 1,
        "code": "shikimori",
        "enabled": True,
        "last_synced_at": last_synced,
    }
    
    # Should run at exact boundary
    assert scheduler.should_run_catalog_sync(source, now) is True


def test_should_not_run_catalog_sync_just_before_boundary(scheduler):
    """Test catalog sync does not run just before interval boundary."""
    now = datetime.now(timezone.utc)
    interval_minutes = scheduler._get_catalog_sync_interval_minutes()
    last_synced = now - timedelta(minutes=interval_minutes - 1)
    
    source = {
        "id": 1,
        "code": "shikimori",
        "enabled": True,
        "last_synced_at": last_synced,
    }
    
    # Should not run yet
    assert scheduler.should_run_catalog_sync(source, now) is False
