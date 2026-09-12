"""
Tests for LogHub Dataset Registry.
Validates that the datasets (Linux, OpenStack, HDFS) are registered, files exist, and can be read programmatically.
"""

import os
import pytest
from backend.data.dataset_registry import DatasetRegistry


def test_registry_domains():
    domains = DatasetRegistry.list_domains()
    assert "operating_systems" in domains
    assert "distributed_systems" in domains


def test_registry_datasets_registered():
    datasets = DatasetRegistry.list_datasets()
    assert len(datasets) == 3
    for k in ["linux", "openstack", "hdfs"]:
        assert k in datasets


@pytest.mark.parametrize("key", ["linux", "openstack", "hdfs"])
def test_dataset_files_exist(key):
    entry = DatasetRegistry.get(key)
    if not os.path.exists(entry.raw_path):
        pytest.skip(
            f"{os.path.basename(entry.raw_path)} is not committed (large LogHub "
            f"download); fetch it into data/samples/ to run this check."
        )
    assert os.path.getsize(entry.raw_path) > 100, f"Raw log too small for {key}"


def test_dataset_read_raw():
    entry = DatasetRegistry.get("linux")
    raw_lines = entry.read_raw(max_lines=25)
    assert len(raw_lines) == 25
    assert all(isinstance(l, str) for l in raw_lines)


def test_full_datasets_when_available():
    openstack = DatasetRegistry.get("openstack")
    assert openstack.raw_path is not None
    assert os.path.exists(openstack.raw_path)
    assert os.path.getsize(openstack.raw_path) > 50_000_000  # ~61.4 MB

    linux = DatasetRegistry.get("linux")
    assert linux.raw_path is not None
    assert os.path.exists(linux.raw_path)
    assert os.path.getsize(linux.raw_path) > 2_000_000  # ~2.3 MB
