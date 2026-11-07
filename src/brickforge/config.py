"""Configuration management for BrickForge.

This module provides typed configuration loading using pydantic-settings.
The configuration is independent from MCP and agent orchestration layers.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BrickForgeConfig(BaseSettings):
    """BrickForge core configuration.

    This configuration class defines all settings required for the core
    BrickForge functionality, including storage paths, database settings,
    and search parameters.

    Attributes:
        app_name: Name of the application.
        debug: Enable debug mode.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        data_dir: Base directory for all data storage.
        db_path: Path to the SQLite database file.
        ingestion_dir: Directory for raw ingestion data.
        processed_dir: Directory for processed brick models.
        search_index_dir: Directory for search index files.
        max_file_size_mb: Maximum file size in MB for ingestion.
        allowed_extensions: List of allowed file extensions for ingestion.
        search_top_k: Default number of results for search queries.
        search_similarity_threshold: Minimum similarity score for search results.
    """

    model_config = SettingsConfigDict(
        env_prefix="BRICKFORGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application settings
    app_name: str = Field(
        default="BrickForge",
        description="Name of the application",
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )

    # Storage paths
    data_dir: Path = Field(
        default=Path("data"),
        description="Base directory for all data storage",
    )
    db_path: Path = Field(
        default=Path("data/brickforge.db"),
        description="Path to the SQLite database file",
    )
    ingestion_dir: Path = Field(
        default=Path("data/ingestion"),
        description="Directory for raw ingestion data",
    )
    processed_dir: Path = Field(
        default=Path("data/processed"),
        description="Directory for processed brick models",
    )
    search_index_dir: Path = Field(
        default=Path("data/search_index"),
        description="Directory for search index files",
    )

    # Ingestion settings
    max_file_size_mb: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum file size in MB for ingestion",
    )
    allowed_extensions: list[str] = Field(
        default=[".json", ".xml", ".csv", ".brd"],
        description="List of allowed file extensions for ingestion",
    )

    # Search settings
    search_top_k: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Default number of results for search queries",
    )
    search_similarity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score for search results",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate that log_level is a valid logging level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}, got {v}")
        return v_upper

    @field_validator("allowed_extensions")
    @classmethod
    def validate_extensions(cls, v: list[str]) -> list[str]:
        """Validate that all extensions start with a dot."""
        for ext in v:
            if not ext.startswith("."):
                raise ValueError(f"Extension must start with a dot: {ext}")
        return v

    @property
    def db_path_resolved(self) -> Path:
        """Return the resolved absolute path to the database file."""
        return self.db_path.resolve()

    @property
    def ingestion_dir_resolved(self) -> Path:
        """Return the resolved absolute path to the ingestion directory."""
        return self.ingestion_dir.resolve()

    @property
    def processed_dir_resolved(self) -> Path:
        """Return the resolved absolute path to the processed directory."""
        return self.processed_dir.resolve()

    @property
    def search_index_dir_resolved(self) -> Path:
        """Return the resolved absolute path to the search index directory."""
        return self.search_index_dir.resolve()

    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.ingestion_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.search_index_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_config() -> BrickForgeConfig:
    """Get the cached BrickForge configuration instance.

    Returns:
        A singleton instance of BrickForgeConfig.
    """
    return BrickForgeConfig()


def reload_config() -> BrickForgeConfig:
    """Clear the configuration cache and reload from environment.

    Returns:
        A fresh instance of BrickForgeConfig.
    """
    get_config.cache_clear()
    return get_config()
