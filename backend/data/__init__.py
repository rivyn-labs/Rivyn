"""
AETHER Data Package.
Provides centralized dataset registries, catalog managers, and log file accessors.
"""

from backend.data.dataset_registry import DatasetRegistry, DatasetEntry

__all__ = ["DatasetRegistry", "DatasetEntry"]
