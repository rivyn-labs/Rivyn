import re
import json
from typing import List, Dict, Any

class LogStructureDetector:
    """
    Detects the log dialect, structural schema, and parsing profile
    from a sample of raw log lines.
    """

    HDFS_PATTERN = re.compile(r'^\d{6}\s+\d{6}\s+\d+\s+(INFO|WARN|ERROR)\s+dfs\.')
    BGL_PATTERN = re.compile(r'^[-\w]+\s+\d{10}\s+\d{4}\.\d{2}\.\d{2}|^\d{4}-\d{2}-\d{2}-\d{2}\.\d{2}\.\d{2}')
    SYSLOG_PATTERN = re.compile(r'^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+[\w\-.]+\s+[\w\-.()/]+(?:\[\d+\])?:')
    OPENSTACK_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+\s+\d+\s+(INFO|WARNING|ERROR|DEBUG)')

    @classmethod
    def detect(cls, sample_lines: List[str]) -> Dict[str, Any]:
        """
        Analyzes sample lines and returns detected dialect, confidence, and recommended parser settings.
        """
        valid_lines = [line.strip() for line in sample_lines if line.strip()]
        if not valid_lines:
            return {"dialect": "generic", "confidence": 0.0, "has_timestamps": False}

        counts = {
            "hdfs": 0,
            "bgl": 0,
            "syslog": 0,
            "openstack": 0,
            "json": 0
        }

        for line in valid_lines[:50]:
            if line.startswith('{') and line.endswith('}'):
                try:
                    json.loads(line)
                    counts["json"] += 1
                    continue
                except Exception:
                    pass

            if cls.HDFS_PATTERN.search(line) or ("dfs.DataNode" in line or "dfs.FSNamesystem" in line):
                counts["hdfs"] += 1
            elif cls.BGL_PATTERN.search(line) or "NULL" in line and ("BGL" in line or "RAS" in line):
                counts["bgl"] += 1
            elif cls.OPENSTACK_PATTERN.search(line) or "req-" in line:
                counts["openstack"] += 1
            elif cls.SYSLOG_PATTERN.search(line) or "sshd" in line:
                counts["syslog"] += 1

        total = len(valid_lines[:50])
        best_dialect, best_count = max(counts.items(), key=lambda x: x[1])

        if best_count / total >= 0.3:
            confidence = round(best_count / total, 2)
            detected = best_dialect
        else:
            detected = "generic"
            confidence = 0.5

        return {
            "dialect": detected,
            "confidence": confidence,
            "sample_count": total,
            "match_breakdown": counts
        }
