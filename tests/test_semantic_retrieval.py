"""
Semantic retrieval backend.

These run whether or not sentence-transformers is installed: the fallback
behaviour is as important as the semantic behaviour, because the base install
deliberately omits the dependency.
"""

import pytest

from backend.ai.embeddings import LogEmbeddingIndex
from backend.ai.semantic_encoder import SemanticEncoder
from backend.normalization.schema import NormalizedLog


def _log(idx, message, service="sshd", level="ERROR"):
    return NormalizedLog(
        id=idx,
        raw=message,
        message=message,
        timestamp="2005-06-04T07:24:32",
        timestamp_epoch=float(1000 + idx),
        level=level,
        service=service,
        host="node-1",
        template=message,
        template_id=f"tpl-{idx}",
        entities={},
        anomaly_score=0.9,
        is_anomaly=True,
    )


CORPUS = [
    _log(1, "authentication failure for user root from 10.0.0.5"),
    _log(2, "PacketResponder terminating for block blk_12345", service="datanode"),
    _log(3, "memory parity error corrected on compute node", service="kernel"),
    _log(4, "instance spawned successfully", service="nova", level="INFO"),
]


def test_index_builds_and_reports_a_backend():
    index = LogEmbeddingIndex(chunk_size=1)
    index.build_index(CORPUS)
    assert index.backend in ("semantic", "tfidf")
    assert index.chunks


def test_search_returns_grounded_chunks():
    index = LogEmbeddingIndex(chunk_size=1)
    index.build_index(CORPUS)
    results = index.search("authentication failure", top_k=2)
    assert results, "lexically identical query must retrieve something"
    top_chunk, score = results[0]
    assert score > 0
    assert any("authentication failure" in l.message for l in top_chunk.logs)


def test_disabling_semantic_forces_tfidf():
    index = LogEmbeddingIndex(chunk_size=1, use_semantic=False)
    index.build_index(CORPUS)
    assert index.encoder is None
    assert index.backend == "tfidf"
    assert index.search("authentication failure", top_k=1)


def test_encoder_reports_reason_when_unavailable():
    """An unavailable backend must explain itself rather than fail silently."""
    encoder = SemanticEncoder()
    if not encoder.is_available:
        assert encoder.unavailable_reason
        assert encoder.backend_name == "tfidf"
    else:
        assert encoder.backend_name.startswith("sentence-transformers:")


@pytest.mark.skipif(
    not SemanticEncoder.shared().is_available,
    reason="sentence-transformers not installed (pip install -r requirements-semantic.txt)",
)
def test_semantic_matches_meaning_not_wording():
    """
    The capability TF-IDF cannot provide: "brute force attack" shares no tokens
    with "authentication failure", so only a dense encoder connects them.
    """
    index = LogEmbeddingIndex(chunk_size=1)
    index.build_index(CORPUS)
    assert index.backend == "semantic"

    results = index.search("brute force login attack", top_k=1)
    assert results
    top_chunk, _ = results[0]
    assert any("authentication failure" in l.message for l in top_chunk.logs), (
        "semantic retrieval should reach the auth-failure line from a query "
        "sharing none of its words"
    )
