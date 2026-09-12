from collections import defaultdict, Counter
from typing import List, Dict, Tuple
from backend.normalization.schema import NormalizedLog

class SequenceMiner:
    """
    Mines sequential template transitions per entity session
    (e.g., HDFS block lifecycle, SSH login attempts, OpenStack request paths)
    and identifies transition breaks or abnormal repetition loops.
    """

    def __init__(self, min_support: int = 2):
        self.min_support = min_support
        self.transition_matrix: Dict[str, Counter] = defaultdict(Counter)

    def extract_entity_sessions(self, logs: List[NormalizedLog]) -> Dict[str, List[NormalizedLog]]:
        sessions: Dict[str, List[NormalizedLog]] = defaultdict(list)
        for log in logs:
            # Check primary entity
            if "block_id" in log.entities:
                sessions[f"block:{log.entities['block_id']}"].append(log)
            elif "req_id" in log.entities:
                sessions[f"req:{log.entities['req_id']}"].append(log)
            elif "user" in log.entities:
                sessions[f"user:{log.entities['user']}"].append(log)
            elif log.host and log.host != "local":
                sessions[f"host:{log.host}"].append(log)
            else:
                sessions[f"svc:{log.service}"].append(log)
        return sessions

    def fit_transitions(self, logs: List[NormalizedLog]):
        sessions = self.extract_entity_sessions(logs)
        for session_id, s_logs in sessions.items():
            templates = [l.template_id for l in s_logs]
            for i in range(len(templates) - 1):
                t1, t2 = templates[i], templates[i+1]
                self.transition_matrix[t1][t2] += 1

    def find_anomalous_sequences(self, logs: List[NormalizedLog]) -> List[Dict[str, any]]:
        self.fit_transitions(logs)
        sessions = self.extract_entity_sessions(logs)
        anomalous_sessions = []

        for session_id, s_logs in sessions.items():
            if len(s_logs) < 2:
                continue

            templates = [l.template_id for l in s_logs]
            unusual_transitions = []
            
            for i in range(len(templates) - 1):
                t1, t2 = templates[i], templates[i+1]
                total_from_t1 = sum(self.transition_matrix[t1].values())
                count_t1_t2 = self.transition_matrix[t1][t2]
                
                # If transition occurs very rarely given t1
                if total_from_t1 >= 3 and count_t1_t2 / total_from_t1 < 0.15:
                    unusual_transitions.append({
                        "from_template": t1,
                        "to_template": t2,
                        "log_id_a": s_logs[i].id,
                        "log_id_b": s_logs[i+1].id,
                        "probability": round(count_t1_t2 / total_from_t1, 3)
                    })

            # Check for excessive repetition (e.g. auth failure burst or retry storm)
            is_burst_retry = len(s_logs) >= 4 and len(set(templates)) == 1

            if unusual_transitions or is_burst_retry:
                anomalous_sessions.append({
                    "session_id": session_id,
                    "event_count": len(s_logs),
                    "first_log_id": s_logs[0].id,
                    "last_log_id": s_logs[-1].id,
                    "unusual_transitions": unusual_transitions,
                    "is_retry_loop": is_burst_retry
                })

        return anomalous_sessions
