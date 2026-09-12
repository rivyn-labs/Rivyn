import re
import hashlib
from typing import List, Dict, Tuple, Optional

class LogCluster:
    def __init__(self, log_template: List[str], log_id: int):
        self.log_template = log_template
        self.template_id = hashlib.md5(" ".join(log_template).encode('utf-8')).hexdigest()[:10]
        self.size = 1
        self.sample_log_ids = [log_id]

    def get_template_str(self) -> str:
        return " ".join(self.log_template)


class Node:
    def __init__(self):
        self.child_nodes: Dict[str, Node] = {}
        self.clusters: List[LogCluster] = []


class DrainParser:
    """
    Drain: An online log parsing algorithm with a fixed-depth parse tree.
    Extracts stable templates from raw unstructured messages by substituting
    dynamic parameters (IPs, numbers, IDs, hex) with wildcard '<*>'
    and extracting params[] for structured binary columnar storage.
    """

    def __init__(self, depth: int = 4, st: float = 0.5, max_child: int = 100):
        self.depth = depth - 2
        self.st = st  # Similarity threshold
        self.max_child = max_child
        self.root = Node()
        self.clusters: Dict[str, LogCluster] = {}

    # Regular expressions to mask dynamic variables before tree traversal
    MASKS = [
        (re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?::\d+)?\b'), '<IP>'),
        (re.compile(r'\bblk_-?\d+\b'), '<BLOCK>'),
        (re.compile(r'\breq-[0-9a-fA-F-]{8,}\b'), '<REQ>'),
        (re.compile(r'\b0x[0-9a-fA-F]+\b'), '<HEX>'),
        (re.compile(r'\b[0-9a-fA-F]{8,}\b'), '<HASH>'),
        (re.compile(r'(/[\w\-.]+)+/?'), '<PATH>'),
        (re.compile(r'\b\d+\b'), '<NUM>'),
    ]

    def preprocess(self, content: str) -> Tuple[List[str], List[str]]:
        cleaned = content
        extracted_params = []
        for regex, token in self.MASKS:
            matches = regex.findall(cleaned)
            for m in matches:
                if isinstance(m, str) and m:
                    extracted_params.append(m)
            cleaned = regex.sub(token, cleaned)
        tokens = cleaned.strip().split()
        return tokens, extracted_params

    def match_template(self, seq1: List[str], seq2: List[str]) -> Tuple[float, int]:
        """Calculates token similarity between two token sequences."""
        if len(seq1) != len(seq2):
            return 0.0, 0
        sim_count = 0
        params = 0
        for token1, token2 in zip(seq1, seq2):
            if token1 == '<*>':
                params += 1
                continue
            if token1 == token2:
                sim_count += 1
        return sim_count / len(seq1), params

    def parse(self, message: str, log_id: int) -> Tuple[str, str, List[str]]:
        """
        Parses a log message into (template_str, template_id, params).
        """
        tokens, params = self.preprocess(message)
        if not tokens:
            return "<EMPTY>", "tmpl_empty", []

        seq_len = len(tokens)
        cur_node = self.root

        # Layer 1: Length layer
        len_key = str(seq_len)
        if len_key not in cur_node.child_nodes:
            cur_node.child_nodes[len_key] = Node()
        cur_node = cur_node.child_nodes[len_key]

        # Layers 2 to depth: Internal token layers
        for i in range(min(self.depth, seq_len)):
            token = tokens[i]
            if token.startswith('<') and token.endswith('>'):
                token = '<*>'
            if token not in cur_node.child_nodes:
                if len(cur_node.child_nodes) >= self.max_child:
                    token = '<*>'
                    if token not in cur_node.child_nodes:
                        cur_node.child_nodes[token] = Node()
                else:
                    cur_node.child_nodes[token] = Node()
            cur_node = cur_node.child_nodes[token]

        # Leaf node: find closest cluster
        best_cluster: Optional[LogCluster] = None
        max_sim = -1.0
        for cluster in cur_node.clusters:
            sim, _ = self.match_template(tokens, cluster.log_template)
            if sim > max_sim:
                max_sim = sim
                best_cluster = cluster

        if max_sim >= self.st and best_cluster is not None:
            # Update existing cluster template with wildcards
            for i, token in enumerate(tokens):
                if best_cluster.log_template[i] != token:
                    best_cluster.log_template[i] = '<*>'
            best_cluster.size += 1
            if len(best_cluster.sample_log_ids) < 10:
                best_cluster.sample_log_ids.append(log_id)
            return best_cluster.get_template_str(), best_cluster.template_id, params
        else:
            # Create a new cluster
            new_template = list(tokens)
            cluster = LogCluster(new_template, log_id)
            cur_node.clusters.append(cluster)
            self.clusters[cluster.template_id] = cluster
            return cluster.get_template_str(), cluster.template_id, params
