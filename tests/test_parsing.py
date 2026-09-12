import pytest
from backend.parsing.timestamp_parser import TimestampParser
from backend.parsing.drain_parser import DrainParser
from backend.parsing.generic_parser import GenericLogParser
from backend.ingestion.loader import LogLoader
from backend.normalization.entity_extractor import EntityExtractor
from backend.normalization.redactor import DataGovernor

def test_timestamp_parser_iso():
    line = "2024-03-10 14:22:01.123 Sample log line"
    iso_ts, epoch, rem = TimestampParser.parse(line)
    assert iso_ts is not None
    assert "2024-03-10" in iso_ts
    assert "Sample log line" in rem

def test_timestamp_parser_hdfs():
    line = "081109 203615 148 INFO dfs.DataNode: testing"
    iso_ts, epoch, rem = TimestampParser.parse(line)
    assert iso_ts is not None
    assert epoch is not None

def test_timestamp_parser_syslog_uses_supplied_dataset_year():
    line = "Jul 09 19:34:06 host sshd[42]: authentication failure"
    iso_ts, epoch, rem = TimestampParser.parse(line, syslog_year=2005)
    assert iso_ts == "2005-07-09T19:34:06"
    assert epoch is not None
    assert "authentication failure" in rem

def test_linux_loghub_dataset_uses_its_provenance_year():
    batch = LogLoader.load_from_lines(
        ["Jul 09 19:34:06 host sshd[42]: authentication failure"],
        dataset_name="linux",
    )
    assert batch.logs[0].timestamp.startswith("2005-")

def test_drain_parser_clustering():
    drain = DrainParser()
    msg1 = "Connection established to worker alpha with status OK"
    msg2 = "Connection established to worker beta with status OK"
    tmpl1, id1, params1 = drain.parse(msg1, 1)
    tmpl2, id2, params2 = drain.parse(msg2, 2)
    assert id1 == id2
    assert "<*>" in tmpl2
    assert isinstance(params1, list)

def test_entity_extractor():
    msg = "serving block blk_987654321 to client 192.168.1.50:50010 user admin"
    entities = EntityExtractor.extract(msg)
    assert entities.get("block_id") == "blk_987654321"
    assert "192.168.1.50" in entities.get("ips", [])
    assert entities.get("user") == "admin"

def test_data_governor_redaction():
    unsafe_log = "User admin logged in with password=SuperSecretToken123! from contact@company.org"
    sanitized = DataGovernor.sanitize(unsafe_log)
    assert "SuperSecretToken123!" not in sanitized
    assert "[REDACTED]" in sanitized
    assert "contact@company.org" not in sanitized
    assert "[EMAIL_REDACTED]" in sanitized
