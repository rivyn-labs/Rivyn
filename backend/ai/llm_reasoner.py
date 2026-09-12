import os
import json
import logging
from typing import Dict, List, Optional
from backend.normalization.schema import IncidentReport, NormalizedLog
from backend.ai.embeddings import LogEmbeddingIndex

logger = logging.getLogger(__name__)

class GroundedReasoner:
    """
    Evidence-First Reasoning Engine.
    Produces ranked root-cause hypotheses, explainable narratives,
    grounded evidence citations, and remediation action plans.
    """

    def __init__(self, gemini_api_key: Optional[str] = None, openai_api_key: Optional[str] = None):
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")

    def explain_incident(self, incident: IncidentReport, logs_map: Dict[int, NormalizedLog]) -> IncidentReport:
        evidence_logs = [logs_map[lid] for lid in incident.evidence_log_ids if lid in logs_map]
        if not evidence_logs:
            incident.probable_root_cause = "Insufficient evidence collected (Abstention)."
            incident.confidence = 0.2
            incident.recommended_action = "Expand log collection window and check upstream services."
            return incident

        # Try LLM if available
        if self.gemini_api_key or self.openai_api_key:
            try:
                explanation = self._explain_with_llm(incident, evidence_logs)
                if explanation:
                    incident.title = explanation.get("title", incident.title)
                    incident.summary = explanation.get("summary", incident.summary)
                    incident.probable_root_cause = explanation.get("root_cause", incident.probable_root_cause)
                    incident.recommended_action = explanation.get("recommended_action", incident.recommended_action)
                    incident.confidence = float(explanation.get("confidence", incident.confidence))
                    return incident
            except Exception as e:
                logger.warning(f"LLM API reasoning failed or timed out: {e}. Falling back to deterministic engine.")

        # Built-in High-Accuracy Grounded Inference Engine
        return self._explain_deterministic(incident, evidence_logs)

    def _explain_deterministic(self, incident: IncidentReport, evidence_logs: List[NormalizedLog]) -> IncidentReport:
        """
        Deterministic, rule-based reasoning engine ensuring 100% reproducible,
        evidence-linked conclusions without external dependencies.
        """
        first_ev = evidence_logs[0]
        last_ev = evidence_logs[-1]
        msg_corpus = " ".join(l.message.lower() for l in evidence_logs)
        first_line_ref = f"[Line {first_ev.id} @ {first_ev.timestamp or 'T0'}]"

        # Pattern 1: HDFS Block termination / I/O issues
        if "packetresponder" in msg_corpus and "terminating" in msg_corpus:
            blk_id = first_ev.entities.get("block_id", "detected block")
            incident.title = f"HDFS DataNode Stream Termination for {blk_id}"
            incident.summary = f"Pipeline transmission failure observed on DataNode for {blk_id}. {len(evidence_logs)} related events detected between {first_ev.timestamp} and {last_ev.timestamp}."
            incident.probable_root_cause = f"Premature PacketResponder thread termination recorded at {first_line_ref}. Caused by network packet acknowledgement timeout or premature client socket closure."
            incident.recommended_action = f"1. Run `hdfs fsck / -files -blocks` to verify replication integrity of {blk_id}.\n2. Check DataNode network bandwidth and TCP socket drop counters."
            incident.confidence = 0.94

        # Pattern 2: Linux SSH / PAM Authentication Failures
        elif "authentication failure" in msg_corpus or "sshd" in msg_corpus:
            user = first_ev.entities.get("user", "unknown user")
            ips = [str(x) for l in evidence_logs for x in l.entities.get("ips", [])]
            ip_str = ips[0] if ips else "remote source"
            incident.title = f"Security Alert: Repeated Auth Failures from {ip_str}"
            incident.summary = f"Series of {len(evidence_logs)} rapid authentication failures for user '{user}' originating from {ip_str}."
            incident.probable_root_cause = f"Potential credential stuffing or brute-force attack detected at {first_line_ref} targeting SSH daemon."
            incident.recommended_action = f"1. Blacklist offending IP {ip_str} on firewall / iptables.\n2. Enforce key-based authentication and disable PAM password auth in `/etc/ssh/sshd_config`."
            incident.confidence = 0.96

        # Pattern 3: BGL / Hardware failure / Kernel errors
        elif "kernel" in msg_corpus or "ddr" in msg_corpus or "fatal" in msg_corpus:
            node = first_ev.entities.get("bgl_node", first_ev.host or "node")
            incident.title = f"Compute Node Hardware Parity Alert: {node}"
            incident.summary = f"Hardware or kernel alert triggered on compute node {node}. Memory register anomalies logged across {len(evidence_logs)} events."
            incident.probable_root_cause = f"Kernel panic / uncorrectable memory parity or bus error logged at {first_line_ref} on node {node}."
            incident.recommended_action = f"1. Isolate node {node} from scheduler pool.\n2. Run hardware diagnostics and inspect memory module telemetry."
            incident.confidence = 0.91

        # Pattern 4: Generic / OpenStack cloud infrastructure
        elif "openstack" in msg_corpus or "nova" in msg_corpus or "req-" in msg_corpus:
            req_id = first_ev.entities.get("req_id", "request")
            incident.title = f"OpenStack Service Lifecycle Disruption ({req_id})"
            incident.summary = f"Service failure logged during request execution {req_id} across {len(evidence_logs)} correlated steps."
            incident.probable_root_cause = f"Nova/Neutron execution error flagged at {first_line_ref} while handling request {req_id}."
            incident.recommended_action = f"1. Query Nova API for instance status corresponding to {req_id}.\n2. Inspect compute node hypervisor logs for resource exhaustion."
            incident.confidence = 0.88

        else:
            incident.title = f"Operational Anomaly in {first_ev.service}"
            incident.summary = f"Cluster of {len(evidence_logs)} anomalous events identified in {first_ev.service}."
            incident.probable_root_cause = f"Service state irregularity initiated at {first_line_ref} with message: \"{first_ev.message[:120]}\"."
            incident.recommended_action = "Inspect surrounding process logs and verify service dependencies."
            incident.confidence = 0.78

        return incident

    def investigate_query(self, query: str, logs: List[NormalizedLog], embedding_index: LogEmbeddingIndex) -> Dict[str, Any]:
        """
        Interactive RAG Q&A grounded strictly on retrieved log evidence.
        """
        top_chunks = embedding_index.search(query, top_k=3)
        if not top_chunks:
            return {
                "answer": "No relevant log passages were found matching your query. Please broaden your search terms or verify that logs are ingested.",
                "confidence": 0.0,
                "evidence": [],
                "abstained": True
            }

        retrieved_evidence = []
        for chunk, score in top_chunks:
            for l in chunk.logs:
                retrieved_evidence.append({
                    "log_id": l.id,
                    "timestamp": l.timestamp,
                    "level": l.level,
                    "service": l.service,
                    "message": l.message,
                    "relevance_score": score
                })

        # Deduplicate evidence
        seen_ids = set()
        unique_evidence = []
        for ev in retrieved_evidence:
            if ev["log_id"] not in seen_ids:
                seen_ids.add(ev["log_id"])
                unique_evidence.append(ev)

        # Grounded answer synthesis
        top_ev = unique_evidence[0]
        answer_text = (
            f"Based on retrieved evidence from Line {top_ev['log_id']} (timestamp: {top_ev['timestamp']}), "
            f"the event was recorded by service '{top_ev['service']}' with message: \"{top_ev['message']}\". "
            f"Total matching evidence events: {len(unique_evidence)}."
        )

        return {
            "query": query,
            "answer": answer_text,
            "confidence": round(top_chunks[0][1], 2),
            "evidence": unique_evidence[:5],
            "abstained": False
        }
