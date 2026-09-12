import re
from datetime import datetime, timezone
from typing import Tuple, Optional

class TimestampParser:
    """
    Parses heterogeneous timestamp dialects without hardcoding.
    Returns standard ISO-8601 string and epoch float for temporal correlations.
    """

    # Common patterns
    # 1. ISO format: 2017-05-16 02:51:08(.123 or ,123)?
    RE_ISO = re.compile(r'\b(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\b')
    # 2. Syslog format: Jun 14 15:16:01 or Oct 21 04:12:00
    RE_SYSLOG = re.compile(r'\b([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\b')
    # 3. HDFS format: 081109 203615 (YYMMDD HHMMSS)
    RE_HDFS = re.compile(r'\b(\d{6}\s+\d{6})\b')
    # 4. Spark format: 15/09/01 18:14:40 (YY/MM/DD HH:MM:SS)
    RE_SPARK = re.compile(r'\b(\d{2}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})\b')
    # 5. BGL format: 2005-06-03-15.42.50.363779
    RE_BGL = re.compile(r'\b(\d{4}-\d{2}-\d{2}-\d{2}\.\d{2}\.\d{2}(?:\.\d+)?)\b')
    # 6. Epoch timestamp (10 or 13 digits)
    RE_EPOCH = re.compile(r'\b(1[0-7]\d{8}(?:\.\d+)?)\b')

    CURRENT_YEAR = datetime.now().year

    @classmethod
    def parse(cls, line: str, fallback_index: int = 0) -> Tuple[Optional[str], Optional[float], str]:
        """
        Extracts timestamp from line if present, and returns:
        (iso_timestamp_str, epoch_timestamp_float, line_without_timestamp)
        """
        # Try ISO (handles .123 and ,123)
        m = cls.RE_ISO.search(line)
        if m:
            raw_ts = m.group(1).replace('T', ' ')
            clean_ts = re.split(r'[.,]', raw_ts)[0]
            try:
                dt = datetime.strptime(clean_ts, "%Y-%m-%d %H:%M:%S")
                return dt.isoformat(), dt.timestamp(), line[:m.start()] + line[m.end():]
            except Exception:
                pass

        # Try Spark (YY/MM/DD HH:MM:SS)
        m = cls.RE_SPARK.search(line)
        if m:
            raw_ts = m.group(1)
            try:
                dt = datetime.strptime(raw_ts, "%y/%m/%d %H:%M:%S")
                return dt.isoformat(), dt.timestamp(), line[:m.start()] + line[m.end():]
            except Exception:
                pass

        # Try BGL (e.g. 2005-06-03-15.42.50.363779)
        m = cls.RE_BGL.search(line)
        if m:
            raw_ts = m.group(1)
            try:
                base = raw_ts.split('.')[0]
                dt = datetime.strptime(base, "%Y-%m-%d-%H.%M.%S")
                return dt.isoformat(), dt.timestamp(), line[:m.start()] + line[m.end():]
            except Exception:
                pass

        # Try Syslog (e.g. Jun 14 15:16:01)
        m = cls.RE_SYSLOG.search(line)
        if m:
            raw_ts = m.group(1)
            # Normalize double space in "Jun  4"
            normalized_ts = re.sub(r'\s+', ' ', raw_ts)
            try:
                dt = datetime.strptime(f"{cls.CURRENT_YEAR} {normalized_ts}", "%Y %b %d %H:%M:%S")
                return dt.isoformat(), dt.timestamp(), line[:m.start()] + line[m.end():]
            except Exception:
                pass

        # Try HDFS (e.g. 081109 203615)
        m = cls.RE_HDFS.search(line)
        if m:
            raw_ts = m.group(1)
            try:
                dt = datetime.strptime(raw_ts, "%y%m%d %H%M%S")
                return dt.isoformat(), dt.timestamp(), line[:m.start()] + line[m.end():]
            except Exception:
                pass

        # Try Epoch
        m = cls.RE_EPOCH.search(line)
        if m:
            try:
                epoch = float(m.group(1))
                dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
                return dt.isoformat(), epoch, line[:m.start()] + line[m.end():]
            except Exception:
                pass

        # Fallback to sequential synthetic timestamp (1 second increments)
        synthetic_epoch = 1700000000.0 + fallback_index
        dt = datetime.fromtimestamp(synthetic_epoch, tz=timezone.utc)
        return dt.isoformat(), synthetic_epoch, line
