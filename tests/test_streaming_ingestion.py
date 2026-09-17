import pyarrow.parquet as pq

from backend.ingestion.streaming import StreamingLogProcessor


def test_streaming_ingestion_writes_all_rows_without_a_full_log_batch(tmp_path):
    source = tmp_path / "large-ish.log"
    lines = []
    for index in range(120):
        level = "ERROR" if index % 15 == 0 else "INFO"
        message = "authentication failure for root" if level == "ERROR" else "normal service heartbeat"
        lines.append(f"Jun  9 06:06:{index % 60:02d} host sshd[{index}]: {level} {message}")
    source.write_text("\n".join(lines), encoding="utf-8")

    batch, stats = StreamingLogProcessor(chunk_lines=20).process_file(
        str(source),
        "linux_bulk_test",
        str(tmp_path / "parquet"),
    )

    assert batch.total_lines == 120
    assert batch.detected_format == "syslog"
    assert len(batch.logs) <= StreamingLogProcessor.MAX_DASHBOARD_LOGS
    assert stats["execution_mode"] == "streaming"
    assert stats["total_rows_scanned"] == 120
    assert stats["anomalies_found"] >= 8
    assert pq.read_table(stats["file_path"]).num_rows == 120
