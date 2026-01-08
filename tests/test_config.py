"""Tests for configuration management."""
import os
import pytest

from oo_automator.config import (
    Config,
    BrowserConfig,
    DatabaseConfig,
    WebConfig,
    get_config,
    reset_config,
)


@pytest.fixture(autouse=True)
def clean_config():
    """Reset config between tests."""
    reset_config()
    yield
    reset_config()


class TestBrowserConfig:
    """Test browser configuration."""

    def test_default_values(self):
        """Test default browser config values."""
        config = BrowserConfig()
        assert config.headless is False
        assert config.max_browsers == 2
        assert config.timeout_ms == 30000
        assert config.retry_attempts == 3


class TestDatabaseConfig:
    """Test database configuration."""

    def test_default_values(self):
        """Test default database config values."""
        config = DatabaseConfig()
        assert config.path == "oo_automator.db"
        assert config.echo is False


class TestWebConfig:
    """Test web server configuration."""

    def test_default_values(self):
        """Test default web config values."""
        config = WebConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 8000


class TestConfig:
    """Test main configuration."""

    def test_default_config(self, monkeypatch):
        """Test default configuration values when no env vars set."""
        # Clear any credentials from environment
        monkeypatch.delenv("OO_EMAIL", raising=False)
        monkeypatch.delenv("OO_PASSWORD", raising=False)

        config = Config()
        assert config.email is None
        assert config.password is None
        assert config.has_credentials() is False

    def test_env_credentials(self, monkeypatch):
        """Test loading credentials from environment."""
        monkeypatch.setenv("OO_EMAIL", "test@example.com")
        monkeypatch.setenv("OO_PASSWORD", "secret123")

        config = Config.load()
        assert config.email == "test@example.com"
        assert config.password == "secret123"
        assert config.has_credentials() is True

    def test_env_browser_settings(self, monkeypatch):
        """Test loading browser settings from environment."""
        monkeypatch.setenv("OO_HEADLESS", "true")
        monkeypatch.setenv("OO_MAX_BROWSERS", "4")

        config = Config.load()
        assert config.browser.headless is True
        assert config.browser.max_browsers == 4

    def test_env_db_path(self, monkeypatch):
        """Test loading database path from environment."""
        monkeypatch.setenv("OO_DB_PATH", "/custom/path.db")

        config = Config.load()
        assert config.database.path == "/custom/path.db"

    def test_env_port(self, monkeypatch):
        """Test loading port from environment."""
        monkeypatch.setenv("OO_PORT", "9000")

        config = Config.load()
        assert config.web.port == 9000


class TestGetConfig:
    """Test get_config singleton."""

    def test_returns_same_instance(self):
        """Test that get_config returns same instance."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_reset_config(self):
        """Test that reset_config clears instance."""
        config1 = get_config()
        reset_config()
        config2 = get_config()
        assert config1 is not config2
