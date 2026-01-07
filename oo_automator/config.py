"""Configuration management for OO Automator."""
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

# Load .env file if dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional


@dataclass
class BrowserConfig:
    """Browser automation configuration."""
    headless: bool = False
    max_browsers: int = 2
    timeout_ms: int = 30000
    retry_attempts: int = 3
    viewport_width: int = 1280
    viewport_height: int = 720


@dataclass
class DatabaseConfig:
    """Database configuration."""
    path: str = "oo_automator.db"
    echo: bool = False


@dataclass
class WebConfig:
    """Web server configuration."""
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = True


@dataclass
class Config:
    """Main application configuration."""
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    web: WebConfig = field(default_factory=WebConfig)

    # Optional credentials (from environment)
    email: Optional[str] = None
    password: Optional[str] = None

    def __post_init__(self):
        """Load environment variables."""
        self.email = os.getenv("OO_EMAIL", self.email)
        self.password = os.getenv("OO_PASSWORD", self.password)

        # Allow env overrides for common settings
        if os.getenv("OO_HEADLESS"):
            self.browser.headless = os.getenv("OO_HEADLESS", "").lower() == "true"
        if os.getenv("OO_MAX_BROWSERS"):
            self.browser.max_browsers = int(os.getenv("OO_MAX_BROWSERS", "2"))
        if os.getenv("OO_DB_PATH"):
            self.database.path = os.getenv("OO_DB_PATH")
        if os.getenv("OO_PORT"):
            self.web.port = int(os.getenv("OO_PORT", "8000"))

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from environment and defaults."""
        return cls()

    def has_credentials(self) -> bool:
        """Check if credentials are configured."""
        return bool(self.email and self.password)


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get global configuration instance."""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def reset_config():
    """Reset configuration (useful for testing)."""
    global _config
    _config = None
