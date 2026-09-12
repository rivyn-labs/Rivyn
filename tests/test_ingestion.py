import os
import pytest
from backend.ingestion.detector import LogStructureDetector
from backend.ingestion.loader import LogLoader
from conftest import dataset_path, dataset_available

def test_structure_detector_hdfs():
    sample = [
        "081109 203615 148 INFO dfs.DataNode$PacketResponder: PacketResponder 1 for block blk_38865049064139660 terminating",
        "081109 203807 222 INFO dfs.DataNode$PacketResponder: PacketResponder 0 for block blk_-6952295868487656571 terminating"
    ]
    res = LogStructureDetector.detect(sample)
    assert res["dialect"] == "hdfs"
    assert res["confidence"] >= 0.5

def test_structure_detector_syslog():
    sample = [
        "Jun 14 15:16:01 combo sshd(pam_unix)[19939]: authentication failure; logname= uid=0 euid=0 tty=NODEVssh ruser= rhost=218.188.2.4",
        "Jun 14 15:16:02 combo sshd(pam_unix)[19937]: check pass; user unknown"
    ]
    res = LogStructureDetector.detect(sample)
    assert res["dialect"] == "syslog"

def test_log_loader_samples():
    present = [n for n in ["Linux.log", "OpenStack.log", "HDFS.log"] if dataset_available(n)]
    assert present, "No sample datasets available in data/samples/"
    for name in present:
        batch = LogLoader.load_from_file(dataset_path(name), max_lines=50)
        assert batch.total_lines > 0
        assert len(batch.logs) == batch.total_lines
        assert len(batch.templates) > 0
