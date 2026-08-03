"""Shared configuration for the multi-agent system."""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    """Central configuration loaded from environment variables."""

    # Orchestrator
    max_concurrent_agents: int = int(os.getenv("MAX_CONCURRENT_AGENTS", "3"))
    agent_timeout_seconds: int = int(os.getenv("AGENT_TIMEOUT_SECONDS", "60"))

    # Financial agent
    financial_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("FINANCIAL_API_KEY")
    )
    financial_symbols: list = field(
        default_factory=lambda: os.getenv("FINANCIAL_SYMBOLS", "AAPL,MSFT,GOOGL").split(",")
    )

    # Job-seeker agent
    job_search_keywords: list = field(
        default_factory=lambda: os.getenv("JOB_SEARCH_KEYWORDS", "software engineer,python").split(",")
    )
    job_search_location: str = os.getenv("JOB_SEARCH_LOCATION", "Remote")
    resume_path: Optional[str] = field(
        default_factory=lambda: os.getenv("RESUME_PATH")
    )

    # Toolchain agent
    toolchain_watch_dirs: list = field(
        default_factory=lambda: os.getenv("TOOLCHAIN_WATCH_DIRS", ".").split(",")
    )
    toolchain_report_path: str = os.getenv("TOOLCHAIN_REPORT_PATH", "reports/toolchain.json")

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: Optional[str] = field(
        default_factory=lambda: os.getenv("LOG_FILE")
    )
