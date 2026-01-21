"""Shared test fixtures and configuration."""
import os

# Set REDIS_URL for tests that import modules requiring Redis
# This prevents import-time errors in modules that create Redis clients
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
