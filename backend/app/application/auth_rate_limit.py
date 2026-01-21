import hashlib
import time
from collections import defaultdict
from typing import DefaultDict, List

AUTH_RATE_LIMIT_MAX_ATTEMPTS = 5
AUTH_RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MESSAGE = "Too many attempts, try again later"
IDENTIFIER_HASH_LENGTH = 64
IP_FALLBACK_LENGTH = 8


class RateLimitExceededError(Exception):
    """Raised when the rate limit is exceeded for a given key."""


class SoftRateLimiter:
    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: DefaultDict[str, List[float]] = defaultdict(list)

    def _prune(self, key: str, now: float) -> List[float]:
        cutoff = now - self.window_seconds
        attempts = [ts for ts in self._attempts.get(key, []) if ts >= cutoff]
        if attempts:
            self._attempts[key] = attempts
        else:
            self._attempts.pop(key, None)
        return attempts

    def is_limited(self, key: str, now: float | None = None) -> bool:
        current = now or time.time()
        attempts = self._prune(key, current)
        return len(attempts) >= self.max_attempts

    def record_failure(self, key: str, now: float | None = None) -> None:
        current = now or time.time()
        attempts = self._prune(key, current)
        attempts.append(current)
        self._attempts[key] = attempts

    def reset(self, key: str) -> None:
        self._attempts.pop(key, None)

    def clear(self) -> None:
        self._attempts.clear()


def _make_key(scope: str, identifier: str, client_ip: str | None) -> str:
    if not identifier:
        raise ValueError("identifier is required for rate limiting")
    identifier_hash = hashlib.sha256(identifier.encode()).hexdigest()
    identifier_component = identifier_hash[:IDENTIFIER_HASH_LENGTH]
    ip_component = client_ip or f"unknown-ip-{identifier_hash[:IP_FALLBACK_LENGTH]}"
    return f"{scope}:{ip_component}:{identifier_component}"


def _ensure_not_limited(limiter: SoftRateLimiter, key: str) -> None:
    if limiter.is_limited(key):
        raise RateLimitExceededError


auth_rate_limiter = SoftRateLimiter(
    max_attempts=AUTH_RATE_LIMIT_MAX_ATTEMPTS,
    window_seconds=AUTH_RATE_LIMIT_WINDOW_SECONDS,
)


def check_login_rate_limit(email: str, client_ip: str | None = None) -> str:
    key = _make_key("login", email.lower(), client_ip)
    _ensure_not_limited(auth_rate_limiter, key)
    return key


def record_login_failure(key: str) -> None:
    auth_rate_limiter.record_failure(key)


def reset_login_limit(key: str) -> None:
    auth_rate_limiter.reset(key)


def check_refresh_rate_limit(token_identifier: str, client_ip: str | None = None) -> str:
    key = _make_key("refresh", token_identifier, client_ip)
    _ensure_not_limited(auth_rate_limiter, key)
    return key


def record_refresh_failure(key: str) -> None:
    auth_rate_limiter.record_failure(key)


def reset_refresh_limit(key: str) -> None:
    auth_rate_limiter.reset(key)
