"""BrickForge Core package.

This package provides the core functionality for BrickForge, including:
- Configuration management
- Ingestion pipeline
- Storage layer
- Search capabilities
- Validation utilities

The core package is independent from MCP and agent orchestration layers.
"""

__version__ = "0.1.0"
__author__ = "BrickForge Team"
__license__ = "MIT"

# Core modules
from brickforge.config import BrickForgeConfig, get_config

__all__ = [
    "BrickForgeConfig",
    "get_config",
    "__version__",
]
