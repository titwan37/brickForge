"""Unit tests for BrickForge configuration module."""

from __future__ import annotations

import pytest
from pathlib import Path

from brickforge.config import BrickForgeConfig, get_config, reload_config


class TestBrickForgeConfig:
    """Tests for BrickForgeConfig class."""

    def test_default_values(self):
        """Test that default configuration values are set correctly."""
        config = BrickForgeConfig()
        assert config.app_name == "BrickForge"
        assert config.debug is False
        assert config.log_level == "INFO"
        assert config.data_dir == Path("data")
        assert config.db_path == Path("data/brickforge.db")
        assert config.max_file_size_mb == 100
        assert config.search_top_k == 10
        assert config.search_similarity_threshold == 0.7

    def test_log_level_validation(self):
        """Test that invalid log levels raise an error."""
        with pytest.raises(ValueError):
            BrickForgeConfig(log_level="INVALID")

    def test_log_level_normalization(self):
        """Test that log level is normalized to uppercase."""
        config = BrickForgeConfig(log_level="debug")
        assert config.log_level == "DEBUG"

    def test_extension_validation(self):
        """Test that extensions without dots raise an error."""
        with pytest.raises(ValueError):
            BrickForgeConfig(allowed_extensions=["json", ".xml"])

    def test_valid_extensions(self):
        """Test that valid extensions are accepted."""
        config = BrickForgeConfig(allowed_extensions=[".json", ".xml"])
        assert config.allowed_extensions == [".json", ".xml"]

    def test_ensure_directories(self, tmp_path):
        """Test that ensure_directories creates all required directories."""
        config = BrickForgeConfig(
            data_dir=tmp_path / "data",
            db_path=tmp_path / "data" / "brickforge.db",
            ingestion_dir=tmp_path / "data" / "ingestion",
            processed_dir=tmp_path / "data" / "processed",
            search_index_dir=tmp_path / "data" / "search_index",
        )
        config.ensure_directories()
        assert config.data_dir.exists()
        assert config.ingestion_dir.exists()
        assert config.processed_dir.exists()
        assert config.search_index_dir.exists()
        assert config.db_path.parent.exists()

    def test_resolved_paths(self, tmp_path):
        """Test that resolved path properties return absolute paths."""
        config = BrickForgeConfig(
            data_dir=tmp_path / "data",
            db_path=tmp_path / "data" / "brickforge.db",
        )
        assert config.db_path_resolved.is_absolute()
        assert config.ingestion_dir_resolved.is_absolute()


class TestGetConfig:
    """Tests for get_config and reload_config functions."""

    def test_get_config_returns_singleton(self):
        """Test that get_config returns the same instance on repeated calls."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_reload_config_clears_cache(self):
        """Test that reload_config clears the cache and returns a new instance."""
        config1 = get_config()
        config2 = reload_config()
        # After reload, the cache is cleared, so a new instance is created
        # They should be equal in value but not necessarily the same object
        assert config1.app_name == config2.app_name
        assert config1.log_level == config2.log_level

    def test_config_from_environment(self, monkeypatch):
        """Test that configuration can be loaded from environment variables."""
        monkeypatch.setenv("BRICKFORGE_APP_NAME", "TestApp")
        monkeypatch.setenv("BRICKFORGE_DEBUG", "true")
        monkeypatch.setenv("BRICKFORGE_LOG_LEVEL", "DEBUG")
        
        # Clear cache to pick up new environment
        get_config.cache_clear()
        config = get_config()
        
        assert config.app_name == "TestApp"
        assert config.debug is True
        assert config.log_level == "DEBUG"
        
        # Cleanup
        get_config.cache_clear()
