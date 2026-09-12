import re
from typing import Dict, Any, List

class EntityExtractor:
    """
    Extracts high-value domain entities across heterogeneous log formats.
    Used for topology correlation, session tracing, and root cause attribution.
    """

    RE_BLOCK = re.compile(r'\b(blk_-?\d+)\b')
    RE_REQ_ID = re.compile(r'\b(req-[0-9a-fA-F-]{8,})\b')
    RE_IPV4 = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')
    RE_USER = re.compile(r'(?i)\b(?:user|username)[=\s]+([a-zA-Z0-9_\-\.]+)\b')
    RE_HEX = re.compile(r'\b(0x[0-9a-fA-F]{4,16})\b')
    RE_BGL_NODE = re.compile(r'\b(R\d{2}-M\d-N\w-C:J\d{2}-U\d{2})\b')
    RE_PORT = re.compile(r':(\d{2,5})\b')

    @classmethod
    def extract(cls, message: str) -> Dict[str, Any]:
        entities: Dict[str, Any] = {}

        # HDFS Block ID
        blocks = cls.RE_BLOCK.findall(message)
        if blocks:
            entities["block_id"] = blocks[0]
            if len(blocks) > 1:
                entities["all_block_ids"] = list(set(blocks))

        # OpenStack Request ID
        reqs = cls.RE_REQ_ID.findall(message)
        if reqs:
            entities["req_id"] = reqs[0]

        # BGL Node Location
        nodes = cls.RE_BGL_NODE.findall(message)
        if nodes:
            entities["bgl_node"] = nodes[0]

        # IP Addresses
        ips = cls.RE_IPV4.findall(message)
        if ips:
            # Filter out subnet masks like 255.255.255.0 if common
            entities["ips"] = list(set(ips))

        # User identification
        user_matches = cls.RE_USER.findall(message)
        if user_matches:
            entities["user"] = user_matches[0]

        # Hex addresses / Registers (Supercomputing / Crashes)
        hexes = cls.RE_HEX.findall(message)
        if hexes:
            entities["memory_registers"] = hexes[:3]

        return entities
