import pytest

# Tests for Settings.from_env() with different ALLOWED_ORIGINS formats


def test_allowed_origins_csv_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that ALLOWED_ORIGINS can be parsed as CSV."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")
    
    from app.config import Settings
    settings = Settings.from_env()
    
    assert settings.allowed_origins == ["http://localhost:3000", "http://localhost:8080"]


def test_allowed_origins_json_array_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that ALLOWED_ORIGINS can be parsed as JSON array."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ALLOWED_ORIGINS", '["http://localhost:3000", "http://localhost:8080"]')
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")
    
    from app.config import Settings
    settings = Settings.from_env()
    
    assert settings.allowed_origins == ["http://localhost:3000", "http://localhost:8080"]


def test_allowed_origins_single_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that ALLOWED_ORIGINS works with a single origin."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")
    
    from app.config import Settings
    settings = Settings.from_env()
    
    assert settings.allowed_origins == ["http://localhost:3000"]


def test_allowed_origins_rejects_wildcard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that ALLOWED_ORIGINS rejects wildcard when credentials are used."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ALLOWED_ORIGINS", "*")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")
    
    from app.config import Settings
    
    with pytest.raises(ValueError, match=r"cannot contain '\*' when credentialed requests"):
        Settings.from_env()


def test_allowed_origins_rejects_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that malformed JSON in ALLOWED_ORIGINS raises an error."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ALLOWED_ORIGINS", '["http://localhost:3000"')
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")
    
    from app.config import Settings
    
    with pytest.raises(ValueError, match="ALLOWED_ORIGINS JSON is malformed"):
        Settings.from_env()


def test_allowed_origins_rejects_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that empty ALLOWED_ORIGINS raises an error."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ALLOWED_ORIGINS", "")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")
    
    from app.config import Settings
    
    with pytest.raises(ValueError, match="ALLOWED_ORIGINS environment variable must be set"):
        Settings.from_env()


def test_allowed_origins_rejects_invalid_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that invalid URLs in ALLOWED_ORIGINS raise an error."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ALLOWED_ORIGINS", "not-a-url,http://localhost:3000")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")
    
    from app.config import Settings
    
    with pytest.raises(ValueError, match="must contain valid http/https origins"):
        Settings.from_env()


def test_allowed_origins_csv_with_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that CSV format handles whitespace correctly."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ALLOWED_ORIGINS", " http://localhost:3000 , http://localhost:8080 ")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")
    
    from app.config import Settings
    settings = Settings.from_env()
    
    assert settings.allowed_origins == ["http://localhost:3000", "http://localhost:8080"]
