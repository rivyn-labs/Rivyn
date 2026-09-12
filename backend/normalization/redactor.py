import re
from typing import Tuple, Dict

class DataGovernor:
    """
    Ensures compliance and data governance as required by MHP:
    - Redacts sensitive credentials, authentication tokens, API keys
    - Pseudonymizes or masks PII (emails, sensitive personal identifiers)
    - Isolates research data while preserving operational forensic utility
    """

    PATTERNS = [
        # Passwords / tokens / secrets
        (re.compile(r'(?i)(password|passwd|pwd|secret|token|api_key|bearer)\s*[:=]\s*([^\s,;]+)'), r'\1=[REDACTED]'),
        # Authorization headers
        (re.compile(r'(?i)authorization:\s*(bearer\s+)?([a-zA-Z0-9_\-\.]{12,})'), r'Authorization: [REDACTED_TOKEN]'),
        # Email addresses
        (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'), r'[EMAIL_REDACTED]'),
        # Private keys / SSH keys
        (re.compile(r'-----BEGIN [A-Z ]+ PRIVATE KEY-----[^-]+-----END [A-Z ]+ PRIVATE KEY-----', re.DOTALL), r'[PRIVATE_KEY_REDACTED]'),
    ]

    @classmethod
    def sanitize(cls, text: str) -> str:
        """Sanitize a raw log text line to remove secrets and PII."""
        if not text:
            return ""
        sanitized = text
        for pattern, replacement in cls.PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized

    @classmethod
    def check_compliance(cls, text: str) -> Dict[str, bool]:
        """Verify compliance against security checks."""
        has_cleartext_creds = bool(re.search(r'(?i)(password|token|secret)\s*[:=]\s*([a-zA-Z0-9!@#$%^&*]{5,})', text))
        has_emails = bool(re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text))
        return {
            "credentials_safe": not has_cleartext_creds,
            "pii_safe": not has_emails,
            "governance_compliant": not (has_cleartext_creds or has_emails)
        }
