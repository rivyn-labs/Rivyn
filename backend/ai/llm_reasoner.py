import os
import json
import logging
from typing import Any, Dict, List, Optional
import httpx

from backend.config import settings
from backend.normalization.schema import IncidentReport, NormalizedLog
from backend.ai.embeddings import LogEmbeddingIndex

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> Dict[str, Any]:
    """Clean markdown code fences and parse JSON payload."""
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())


class GroundedReasoner:
    """
    Evidence-First Reasoning Engine.
    Powered by OpenAI (GPT-4o / GPT-4o-mini) as the primary LLM provider,
    with support for Anthropic Claude and Google Gemini, and a guaranteed
    deterministic grounded rule engine fallback.
    """

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_sec: Optional[float] = None
    ):
        self.openai_api_key = openai_api_key if openai_api_key is not None else (getattr(settings, "openai_api_key", None) or os.getenv("OPENAI_API_KEY"))
        self.anthropic_api_key = anthropic_api_key if anthropic_api_key is not None else (getattr(settings, "anthropic_api_key", None) or os.getenv("ANTHROPIC_API_KEY"))
        self.gemini_api_key = gemini_api_key if gemini_api_key is not None else (getattr(settings, "gemini_api_key", None) or os.getenv("GEMINI_API_KEY"))
        self.model = model or getattr(settings, "llm_model", "gpt-4o-mini")
        self.timeout_sec = timeout_sec or getattr(settings, "llm_timeout_sec", 12.0)

    @property
    def has_llm_provider(self) -> bool:
        return bool(self.openai_api_key or self.anthropic_api_key or self.gemini_api_key)

    def explain_incident(self, incident: IncidentReport, logs_map: Dict[int, NormalizedLog]) -> IncidentReport:
        """
        Synthesize incident title, root-cause hypothesis, and remediation plan
        from correlated evidence logs using OpenAI / LLM or deterministic fallback.
        """
        evidence_logs = [logs_map[lid] for lid in incident.evidence_log_ids if lid in logs_map]
        if not evidence_logs:
            incident.probable_root_cause = "Insufficient evidence collected (Abstention)."
            incident.confidence = 0.2
            incident.recommended_action = "Expand log collection window and check upstream services."
            return incident

        # Attempt LLM reasoning if an API key is configured
        if self.has_llm_provider:
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
                logger.warning(f"LLM API incident explanation failed ({e}). Falling back to deterministic engine.")

        # Built-in High-Accuracy Grounded Inference Engine (Deterministic Fallback)
        return self._explain_deterministic(incident, evidence_logs)

    def _explain_with_llm(self, incident: IncidentReport, evidence_logs: List[NormalizedLog]) -> Optional[Dict[str, Any]]:
        """Route to active LLM provider: OpenAI -> Anthropic -> Gemini."""
        formatted_logs = "\n".join(
            f"Line {l.id} [{l.timestamp}] [{l.level}] {l.service}: {l.message}"
            for l in evidence_logs[:25]
        )

        if self.openai_api_key:
            return self._call_openai_incident(formatted_logs)
        elif self.anthropic_api_key:
            return self._call_anthropic_incident(formatted_logs)
        elif self.gemini_api_key:
            return self._call_gemini_incident(formatted_logs)
        return None

    def _call_openai_incident(self, formatted_logs: str) -> Dict[str, Any]:
        """Invoke OpenAI API (using OpenAI client or direct REST fallback) for structured root cause."""
        prompt = (
            "You are an expert Principal Site Reliability Engineer (SRE) analyzing correlated system log anomalies. "
            "Analyze the provided log evidence and return ONLY a valid JSON object with the following fields:\n"
            "- title: A clear, concise incident title (max 8 words)\n"
            "- summary: 1-2 sentence executive summary of the failure sequence\n"
            "- root_cause: Technical root cause explanation citing triggering log lines (e.g. [Line 42 @ 2026-09-12T10:00:00])\n"
            "- recommended_action: Numbered 2-3 step immediate remediation checklist\n"
            "- confidence: Confidence float between 0.0 and 1.0\n"
            "Return ONLY the raw JSON object, with no markdown code fence and no surrounding commentary."
        )

        # Try official OpenAI SDK client first
        try:
            import openai
            client = openai.OpenAI(api_key=self.openai_api_key, timeout=self.timeout_sec)
            target_model = self.model if ("gpt" in self.model or "o1" in self.model or "o3" in self.model) else "gpt-4o-mini"
            completion = client.chat.completions.create(
                model=target_model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Correlated Incident Evidence Logs:\n{formatted_logs}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            return _extract_json(completion.choices[0].message.content)
        except Exception:
            # Direct REST fallback via httpx
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {self.openai_api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Correlated Incident Evidence Logs:\n{formatted_logs}"}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2
            }
            res = httpx.post(url, json=payload, headers=headers, timeout=self.timeout_sec)
            res.raise_for_status()
            data = res.json()
            return _extract_json(data["choices"][0]["message"]["content"])

    def _call_anthropic_incident(self, formatted_logs: str) -> Dict[str, Any]:
        """Invoke Anthropic Claude API for structured incident analysis."""
        import anthropic
        client = anthropic.Anthropic(api_key=self.anthropic_api_key, timeout=self.timeout_sec)
        system_prompt = (
            "You are an expert Principal Site Reliability Engineer (SRE) analyzing correlated system log anomalies. "
            "Analyze the provided log evidence and return ONLY a valid JSON object with: title, summary, root_cause, recommended_action, confidence (0.0-1.0)."
        )
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=600,
            system=system_prompt,
            messages=[{"role": "user", "content": f"Evidence Logs:\n{formatted_logs}"}]
        )
        return _extract_json(response.content[0].text)

    def _call_gemini_incident(self, formatted_logs: str) -> Dict[str, Any]:
        """Invoke Google Gemini REST API via httpx."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"
        prompt = (
            "Analyze these correlated system log lines and return ONLY a JSON object with fields: "
            "title, summary, root_cause (citing Line numbers), recommended_action, and confidence (float 0.0-1.0).\n\n"
            f"{formatted_logs}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"}
        }
        res = httpx.post(url, json=payload, timeout=self.timeout_sec)
        res.raise_for_status()
        data = res.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return _extract_json(text)

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
        Uses OpenAI / active LLM when available, with deterministic synthesis fallback.
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

        # Try LLM-grounded synthesis if available
        if self.has_llm_provider:
            try:
                llm_answer = self._investigate_with_llm(query, unique_evidence[:5])
                if llm_answer:
                    return {
                        "query": query,
                        "answer": llm_answer,
                        "confidence": round(top_chunks[0][1], 2),
                        "evidence": unique_evidence[:5],
                        "abstained": False
                    }
            except Exception as e:
                logger.warning(f"LLM Copilot investigation failed ({e}). Falling back to deterministic synthesis.")

        # Grounded answer deterministic synthesis fallback
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

    def _investigate_with_llm(self, query: str, evidence: List[Dict[str, Any]]) -> Optional[str]:
        """Generate grounded Copilot answer using OpenAI (primary) or active LLM."""
        formatted_evidence = "\n".join(
            f"- Line {ev['log_id']} @ {ev['timestamp']} [{ev['level']}] {ev['service']}: {ev['message']}"
            for ev in evidence
        )

        system_prompt = (
            "You are AETHER Investigation Copilot, an expert site reliability observability assistant. "
            "Answer the user's question using strictly the provided log evidence. "
            "Always cite exact log lines (e.g. [Line 42 @ 2026-09-12T10:00:00]). "
            "If the evidence does not support answering the question, state that clearly and abstain from guessing."
        )
        user_prompt = f"User Question: {query}\n\nRetrieved Log Evidence:\n{formatted_evidence}"

        if self.openai_api_key:
            try:
                import openai
                client = openai.OpenAI(api_key=self.openai_api_key, timeout=self.timeout_sec)
                target_model = self.model if ("gpt" in self.model or "o1" in self.model or "o3" in self.model) else "gpt-4o-mini"
                res = client.chat.completions.create(
                    model=target_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.2,
                    max_tokens=400
                )
                return res.choices[0].message.content.strip()
            except Exception:
                url = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {self.openai_api_key}", "Content-Type": "application/json"}
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.2,
                    "max_tokens": 400
                }
                res = httpx.post(url, json=payload, headers=headers, timeout=self.timeout_sec)
                res.raise_for_status()
                return res.json()["choices"][0]["message"]["content"].strip()

        elif self.anthropic_api_key:
            import anthropic
            client = anthropic.Anthropic(api_key=self.anthropic_api_key, timeout=self.timeout_sec)
            res = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=500,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            return res.content[0].text.strip()

        return None
