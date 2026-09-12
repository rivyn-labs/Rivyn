"""
Tests for LogHub Dataset Registry and System Organization.
Validates that all 16 datasets are registered, files exist, and can be read programmatically.
"""

import os
import pytest
from backend.data.dataset_registry import DatasetRegistry


def test_registry_domains():
    domains = DatasetRegistry.list_domains()
    expected = [
        "distributed_systems",
        "mobile_systems",
        "operating_systems",
        "server_applications",
        "supercomputers",
    ]
    assert sorted(domains) == sorted(expected)


def test_registry_all_16_datasets_registered():
    datasets = DatasetRegistry.list_datasets()
    assert len(datasets) == 16
    expected_keys = [
        "hdfs", "hadoop", "spark", "zookeeper", "openstack",
        "bgl", "hpc", "thunderbird",
        "linux", "mac", "windows",
        "android", "healthapp",
        "apache", "openssh", "proxifier",
    ]
    for k in expected_keys:
        assert k in datasets


@pytest.mark.parametrize("key", [
    "hdfs", "hadoop", "spark", "zookeeper", "openstack",
    "bgl", "hpc", "thunderbird",
    "linux", "mac", "windows",
    "android", "healthapp",
    "apache", "openssh", "proxifier",
])
def test_dataset_files_exist(key):
    entry = DatasetRegistry.get(key)
    assert os.path.exists(entry.raw_2k_path), f"Raw 2k log missing for {key}: {entry.raw_2k_path}"
    assert os.path.getsize(entry.raw_2k_path) > 100, f"Raw 2k log too small for {key}"
    assert entry.structured_csv_path and os.path.exists(entry.structured_csv_path), f"Structured CSV missing for {key}"
    assert entry.templates_csv_path and os.path.exists(entry.templates_csv_path), f"Templates CSV missing for {key}"
    assert os.path.exists(entry.readme_path), f"README missing for {key}"


def test_dataset_read_raw_and_structured():
    entry = DatasetRegistry.get("hdfs")
    raw_lines = entry.read_raw(max_lines=25)
    assert len(raw_lines) == 25
    assert all(isinstance(l, str) for l in raw_lines)

    df_struct = entry.read_structured()
    assert len(df_struct) >= 2000
    assert "EventTemplate" in df_struct.columns or "EventId" in df_struct.columns

    df_templates = entry.read_templates()
    assert len(df_templates) > 0


def test_full_datasets_when_available():
    openstack = DatasetRegistry.get("openstack")
    assert openstack.raw_full_path is not None
    assert os.path.exists(openstack.raw_full_path)
    assert os.path.getsize(openstack.raw_full_path) > 50_000_000  # 61.4 MB

    linux = DatasetRegistry.get("linux")
    assert linux.raw_full_path is not None
    assert os.path.exists(linux.raw_full_path)
    assert os.path.getsize(linux.raw_full_path) > 2_000_000  # 2.3 MB
