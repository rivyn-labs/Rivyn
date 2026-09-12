import pytest
from backend.parsing.timestamp_parser import TimestampParser
from backend.parsing.drain_parser import DrainParser
from backend.parsing.generic_parser import GenericLogParser
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

def test_drain_parser_clustering():
    drain = DrainParser()
    msg1 = "Connection established to worker alpha with status OK"
    msg2 = "Connection established to worker beta with status OK"
    tmpl1, id1 = drain.parse(msg1, 1)
    tmpl2, id2 = drain.parse(msg2, 2)
    assert id1 == id2
    assert "<*>" in tmpl2

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
