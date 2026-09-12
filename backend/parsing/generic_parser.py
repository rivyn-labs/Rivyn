import re
from typing import Optional, Dict, Any
from backend.normalization.schema import NormalizedLog, LogSeverity
from backend.normalization.redactor import DataGovernor
from backend.normalization.entity_extractor import EntityExtractor
from backend.parsing.timestamp_parser import TimestampParser
from backend.parsing.drain_parser import DrainParser

class GenericLogParser:
    """
    Adaptive, multi-format log parser.
    Converts raw text lines into standardized NormalizedLog records
    using automatic dialect recognition, fuzzy timestamp extraction,
    and Drain tree-based template discovery.
    """

    SEVERITY_MAP = {
        "DEBUG": LogSeverity.DEBUG,
        "INFO": LogSeverity.INFO,
        "WARN": LogSeverity.WARN,
        "WARNING": LogSeverity.WARN,
        "ERROR": LogSeverity.ERROR,
        "ERR": LogSeverity.ERROR,
        "FATAL": LogSeverity.FATAL,
        "CRITICAL": LogSeverity.CRITICAL,
        "SEVERE": LogSeverity.CRITICAL,
        "FAILURE": LogSeverity.ERROR,
        "FAILED": LogSeverity.ERROR
    }

    RE_LEVEL = re.compile(r'\b(DEBUG|INFO|NOTICE|WARN(?:ING)?|ERROR|ERR|FATAL|CRITICAL|SEVERE|FAILURE|FAILED)\b', re.IGNORECASE)

    def __init__(self, syslog_year: Optional[int] = None):
        self.drain = DrainParser(depth=4, st=0.5)
        self.syslog_year = syslog_year

    def parse_line(self, line: str, line_id: int, dialect: str = "generic") -> NormalizedLog:
        raw_clean = line.strip()
        
        # 1. Compliance Sanitization
        sanitized_raw = DataGovernor.sanitize(raw_clean)

        # 2. Extract Timestamp
        iso_ts, epoch_ts, rem_line = TimestampParser.parse(
            sanitized_raw,
            fallback_index=line_id,
            syslog_year=self.syslog_year,
        )

        # 3. Detect Severity / Level
        level = LogSeverity.INFO.value
        level_match = self.RE_LEVEL.search(rem_line)
        if level_match:
            raw_lvl = level_match.group(1).upper()
            level = self.SEVERITY_MAP.get(raw_lvl, LogSeverity.INFO).value

        # 4. Extract Service / Host / Component based on Dialect
        service = "system"
        host = "local"
        pid = None
        message = rem_line

        if dialect == "hdfs":
            # 081109 203615 148 INFO dfs.DataNode$PacketResponder: PacketResponder 1 for block ...
            parts = rem_line.split(':', 1)
            if len(parts) == 2:
                header, body = parts
                message = body.strip()
                tokens = header.split()
                for token in tokens:
                    if "dfs." in token:
                        service = token
                    elif token.isdigit() and pid is None:
                        pid = token
            else:
                message = rem_line

        elif dialect == "syslog":
            # Jun 14 15:16:01 combo sshd(pam_unix)[19939]: authentication failure...
            parts = rem_line.split(':', 1)
            if len(parts) == 2:
                header, body = parts
                message = body.strip()
                tokens = header.split()
                if len(tokens) >= 2:
                    host = tokens[0]
                    proc_part = tokens[1]
                    # Parse proc and pid e.g. sshd[1234] or sshd(pam)[1234]
                    pid_match = re.search(r'\[(\d+)\]', proc_part)
                    if pid_match:
                        pid = pid_match.group(1)
                    service = re.sub(r'\[\d+\]', '', proc_part)
            else:
                message = rem_line

        elif dialect == "openstack":
            # 2017-05-16 02:51:08.270 25746 INFO nova.osapi_compute... [req-...] ...
            tokens = rem_line.split()
            if len(tokens) >= 3:
                for token in tokens[:5]:
                    if "nova." in token or "cinder." in token or "glance." in token:
                        service = token
                        break
                for token in tokens[:4]:
                    if token.isdigit():
                        pid = token
                        break
            message = rem_line

        elif dialect == "bgl":
            # - 1117838570 2005.06.03 R02-M1-N0-C:J12-U11 2005-06-03-15.42.50.363779 R02-M1-N0-C:J12-U11 RAS KERNEL INFO instruction cache parity error corrected
            tokens = rem_line.split()
            for token in tokens:
                if re.match(r'R\d{2}-M\d', token):
                    host = token
                if token in ["KERNEL", "APP", "DISCOVERY", "RAS"]:
                    service = token
            lvl_match = self.RE_LEVEL.search(rem_line)
            if lvl_match:
                message = rem_line[lvl_match.end():].strip()
            else:
                message = rem_line

        elif dialect == "zookeeper":
            # 2015-07-29 17:41:41,536 - INFO  [main:QuorumPeerConfig@101] - Reading configuration from: /etc/zookeeper/conf/zoo.cfg
            match = re.search(r'\[([^\]]+)\]\s*-\s*(.+)$', rem_line)
            if match:
                comp_info = match.group(1)
                message = match.group(2).strip()
                if ':' in comp_info:
                    service = comp_info.split(':')[1].split('@')[0]
                else:
                    service = comp_info.split('@')[0]
            else:
                message = rem_line

        elif dialect == "hadoop":
            # 2015-10-17 15:37:56,547 INFO [main] org.apache.hadoop.mapreduce.v2.app.MRAppMaster: Created MRAppMaster for application
            parts = rem_line.split(':', 1)
            if len(parts) == 2:
                header, body = parts
                message = body.strip()
                tokens = header.split()
                for token in tokens:
                    if "org.apache.hadoop" in token or "mapred" in token or "MRAppMaster" in token:
                        service = token.split('.')[-1]
            else:
                message = rem_line

        elif dialect == "spark":
            # 15/09/01 18:14:40 INFO executor.CoarseGrainedExecutorBackend: Registered signal handlers for [TERM, HUP, INT]
            parts = rem_line.split(':', 1)
            if len(parts) == 2:
                header, body = parts
                message = body.strip()
                tokens = header.split()
                for token in tokens:
                    if "." in token or "executor" in token or "spark" in token:
                        service = token.split('.')[-1]
            else:
                message = rem_line

        # Clean remaining message
        message = re.sub(r'^\s*[-:]+\s*', '', message).strip()
        if not message:
            message = sanitized_raw

        # 5. Extract Operational Entities
        entities = EntityExtractor.extract(sanitized_raw)
        if "bgl_node" in entities and host == "local":
            host = entities["bgl_node"]

        # 6. Drain Template Mining
        template_str, template_id, params = self.drain.parse(message, line_id)

        # 7. Initial Anomaly Flagging for critical severities
        is_initial_anomaly = level in ["ERROR", "FATAL", "CRITICAL"]

        return NormalizedLog(
            id=line_id,
            timestamp=iso_ts,
            timestamp_epoch=epoch_ts,
            level=level,
            service=service,
            host=host,
            pid=pid,
            message=message,
            template=template_str,
            template_id=template_id,
            params=params,
            entities=entities,
            raw=sanitized_raw,
            anomaly_score=0.8 if is_initial_anomaly else 0.0,
            is_anomaly=is_initial_anomaly
        )
