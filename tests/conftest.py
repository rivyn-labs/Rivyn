import os
import sys

import pytest

# Ensure backend can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Datasets too large to commit. LogHub distributes these as archives rather than
# raw files, so `scripts/download_datasets.py` cannot fetch them unattended and a
# fresh clone will not have them. Tests that need one skip with an actionable
# message instead of failing, so a clean checkout reports honest results.
OPTIONAL_LARGE_DATASETS = {
    "HDFS.log": (
        "HDFS.log (1.58 GB) is not committed. Download it from "
        "https://github.com/logpai/loghub and place it in data/samples/ "
        "to run this test."
    ),
}


def dataset_path(filename: str) -> str:
    """
    Absolute path to a dataset in data/samples, skipping the test when the file
    is absent and known to be an optional large download.
    """
    path = os.path.join(REPO_ROOT, "data", "samples", filename)
    if not os.path.exists(path):
        reason = OPTIONAL_LARGE_DATASETS.get(
            filename, f"Dataset data/samples/{filename} is missing."
        )
        pytest.skip(reason, allow_module_level=False)
    return path


def dataset_available(filename: str) -> bool:
    """Non-skipping existence check, for tests that iterate over datasets."""
    return os.path.exists(os.path.join(REPO_ROOT, "data", "samples", filename))
