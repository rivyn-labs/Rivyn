import copy
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from backend.api.state import state
from backend.config import settings
from backend.ingestion.incremental import IncrementalIngestor
from backend.storage.binary_engine import BinaryLogEngine


ERRORS = [
    "2024-01-01 00:00:01 ERROR api: request req-12345678 failed for user alice",
    "2024-01-01 00:00:02 ERROR api: request req-12345678 failed for user alice",
]
LATER = ["2024-01-01 00:00:03 ERROR api: request req-12345678 failed for user alice"]


@pytest.fixture(autouse=True)
def isolated_ingestion_state():
    previous = (state.current_batch, state.embedding_index, state.binary_stats, state.datasets)
    state.current_batch = None
    state.embedding_index = None
    state.binary_stats = None
    state.datasets = {}
    yield
    state.current_batch, state.embedding_index, state.binary_stats, state.datasets = previous


def ingest(lines, tmp_path, dataset="incremental", offset=0):
    return IncrementalIngestor.ingest(
        lines, dataset, source_id="service.log", source_line_offset=offset, output_dir=str(tmp_path)
    )


def test_first_ingestion_creates_complete_dataset(tmp_path):
    batch = ingest(ERRORS, tmp_path)
    assert batch.total_lines == 2
    assert {log.source_line for log in batch.logs} == {1, 2}
    assert len(state.datasets["incremental"].event_ids) == 2


def test_second_ingestion_merges_only_new_records(tmp_path):
    first = ingest(ERRORS, tmp_path)
    second = ingest(LATER, tmp_path, offset=2)
    assert second.total_lines == 3
    assert [log.id for log in second.logs] == [1, 2, 3]
    assert [log.event_id for log in second.logs[:2]] == [log.event_id for log in first.logs]


def test_duplicate_upload_is_idempotent(tmp_path):
    first = ingest(ERRORS, tmp_path)
    second = ingest(ERRORS, tmp_path)
    assert second.total_lines == first.total_lines == 2
    assert pq.read_table(state.binary_stats["file_path"]).num_rows == 2


def test_later_slice_preserves_source_line_identity(tmp_path):
    ingest(ERRORS, tmp_path)
    batch = ingest(LATER, tmp_path, offset=2)
    assert batch.logs[-1].source_line == 3
    assert batch.logs[-1].id == 3
    assert batch.total_lines == 3


def test_drain_templates_persist_between_ingestions(tmp_path):
    first = ingest(ERRORS[:1], tmp_path)
    template_id = first.logs[0].template_id
    second = ingest(ERRORS[1:], tmp_path, offset=1)
    assert second.logs[-1].template_id == template_id
    assert template_id in second.templates


def test_incidents_persist_and_accept_new_evidence(tmp_path):
    first = ingest(ERRORS, tmp_path)
    first_ids = [incident.id for incident in first.incidents]
    assert first_ids
    second = ingest(LATER, tmp_path, offset=2)
    assert first_ids[0] in [incident.id for incident in second.incidents]
    persisted = next(incident for incident in second.incidents if incident.id == first_ids[0])
    assert 3 in persisted.evidence_log_ids


def test_embedding_chunks_persist_and_grow(tmp_path):
    ingest(ERRORS, tmp_path)
    old_chunk_ids = [chunk.chunk_id for chunk in state.embedding_index.chunks]
    ingest(LATER, tmp_path, offset=2)
    new_chunk_ids = [chunk.chunk_id for chunk in state.embedding_index.chunks]
    assert set(old_chunk_ids).issubset(new_chunk_ids)
    assert len(new_chunk_ids) > len(old_chunk_ids)


def test_parquet_rows_persist_and_append(tmp_path):
    ingest(ERRORS, tmp_path)
    path = state.binary_stats["file_path"]
    first_events = pq.read_table(path)["event_id"].to_pylist()
    ingest(LATER, tmp_path, offset=2)
    table = pq.read_table(path)
    assert table.num_rows == 3
    assert table["event_id"].to_pylist()[:2] == first_events


def test_failed_ingestion_does_not_publish_partial_state(tmp_path, monkeypatch):
    first = ingest(ERRORS, tmp_path)
    before = copy.deepcopy(first)
    parquet_path = Path(state.binary_stats["file_path"])
    parquet_before = parquet_path.read_bytes()

    def fail_save(*args, **kwargs):
        raise OSError("simulated parquet failure")

    monkeypatch.setattr(BinaryLogEngine, "save_batch", fail_save)
    with pytest.raises(OSError, match="simulated"):
        ingest(LATER, tmp_path, offset=2)
    assert state.datasets["incremental"].batch.model_dump() == before.model_dump()
    assert parquet_path.read_bytes() == parquet_before


def test_datasets_are_isolated(tmp_path):
    left = ingest(ERRORS, tmp_path, dataset="left")
    right = ingest(LATER, tmp_path, dataset="right")
    assert left.total_lines == 2
    assert right.total_lines == 1
    assert state.datasets["left"].batch.total_lines == 2
    assert state.datasets["right"].batch.total_lines == 1


def test_changed_incidents_use_configured_llm_with_a_bounded_budget(tmp_path, monkeypatch):
    import backend.ingestion.incremental as incremental

    calls = []

    class FakeReasoner:
        def explain_incident(self, incident, logs_map):
            calls.append((incident.id, sorted(logs_map)))
            incident.title = "LLM-grounded diagnosis"
            return incident

    monkeypatch.setattr(incremental, "GroundedReasoner", FakeReasoner)
    monkeypatch.setattr(settings, "llm_max_incidents_per_ingestion", 1)

    batch = ingest(ERRORS, tmp_path)

    assert calls
    assert len(calls) == 1
    assert batch.incidents[0].title == "LLM-grounded diagnosis"
