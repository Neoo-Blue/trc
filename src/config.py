"""Configuration module for TRC - The Riven Companion."""

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

# Load .env file if present
load_dotenv()


@dataclass
class Config:
    """Application configuration loaded from environment variables."""
    
    # Riven Configuration
    riven_url: str = field(default_factory=lambda: os.getenv("RIVEN_URL", "http://localhost:8083"))
    riven_api_key: str = field(default_factory=lambda: os.getenv("RIVEN_API_KEY", ""))
    
    # Real-Debrid Configuration
    rd_api_key: str = field(default_factory=lambda: os.getenv("RD_API_KEY", ""))
    rd_base_url: str = "https://api.real-debrid.com/rest/1.0"
    
    # Monitoring Intervals (in seconds)
    check_interval_hours: float = field(default_factory=lambda: float(os.getenv("CHECK_INTERVAL_HOURS", "6")))
    retry_interval_minutes: float = field(default_factory=lambda: float(os.getenv("RETRY_INTERVAL_MINUTES", "10")))
    rd_check_interval_minutes: float = field(default_factory=lambda: float(os.getenv("RD_CHECK_INTERVAL_MINUTES", "5")))
    rd_max_wait_hours: float = field(default_factory=lambda: float(os.getenv("RD_MAX_WAIT_HOURS", "2")))
    rd_cleanup_interval_hours: float = field(default_factory=lambda: float(os.getenv("RD_CLEANUP_INTERVAL_HOURS", "1")))
    rd_stuck_torrent_hours: float = field(default_factory=lambda: float(os.getenv("RD_STUCK_TORRENT_HOURS", "24")))
    
    # Retry Configuration
    max_riven_retries: int = field(default_factory=lambda: int(os.getenv("MAX_RIVEN_RETRIES", "3")))
    max_rd_torrents: int = field(default_factory=lambda: int(os.getenv("MAX_RD_TORRENTS", "10")))
    max_active_rd_downloads: int = field(default_factory=lambda: int(os.getenv("MAX_ACTIVE_RD_DOWNLOADS", "3")))
    torrent_add_delay_seconds: int = field(default_factory=lambda: int(os.getenv("TORRENT_ADD_DELAY_SECONDS", "30")))

    # Skip remove+add retry and go directly to manual scrape (for testing)
    skip_riven_retry: bool = field(default_factory=lambda: os.getenv("SKIP_RIVEN_RETRY", "false").lower() in ("true", "1", "yes"))

    # Skip RD validation on startup (for testing Riven integration only)
    skip_rd_validation: bool = field(default_factory=lambda: os.getenv("SKIP_RD_VALIDATION", "false").lower() in ("true", "1", "yes"))
    
    # Rate Limiting (max 12 API calls per minute = 1 call per 5 seconds minimum)
    rd_rate_limit_seconds: float = field(default_factory=lambda: float(os.getenv("RD_RATE_LIMIT_SECONDS", "5")))
    riven_rate_limit_seconds: float = field(default_factory=lambda: float(os.getenv("RIVEN_RATE_LIMIT_SECONDS", "1")))
    
    # States to monitor
    problem_states: list = field(default_factory=lambda: ["Failed", "Unknown"])
    
    # Logging
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    
    @property
    def check_interval_seconds(self) -> float:
        return self.check_interval_hours * 3600
    
    @property
    def retry_interval_seconds(self) -> float:
        return self.retry_interval_minutes * 60
    
    @property
    def rd_check_interval_seconds(self) -> float:
        return self.rd_check_interval_minutes * 60
    
    @property
    def rd_max_wait_seconds(self) -> float:
        return self.rd_max_wait_hours * 3600

    @property
    def rd_cleanup_interval_seconds(self) -> float:
        return self.rd_cleanup_interval_hours * 3600

    @property
    def rd_stuck_torrent_seconds(self) -> float:
        return self.rd_stuck_torrent_hours * 3600

    def validate(self) -> bool:
        """Validate required configuration."""
        if not self.riven_api_key:
            raise ValueError("RIVEN_API_KEY is required")
        if not self.rd_api_key:
            raise ValueError("RD_API_KEY is required")
        return True


def load_config() -> Config:
    """Load and validate configuration."""
    config = Config()
    config.validate()
    return config

