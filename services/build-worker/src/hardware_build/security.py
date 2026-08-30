from __future__ import annotations

import re
from typing import Any

from .settings import Settings

REDACTED = "[REDACTED]"
_CREDENTIAL_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)((?:api[_-]?key|token|secret|password)\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
)


def redact_text(value: str, settings: Settings) -> str:
    redacted = value
    for secret in settings.secret_values:
        redacted = redacted.replace(secret, REDACTED)
    for pattern in _CREDENTIAL_PATTERNS:
        redacted = pattern.sub(lambda match: f"{match.group(1)}{REDACTED}" if match.lastindex else REDACTED, redacted)
    return redacted


def redact(value: Any, settings: Settings) -> Any:
    if isinstance(value, str):
        return redact_text(value, settings)
    if isinstance(value, dict):
        return {key: redact(item, settings) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, settings) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item, settings) for item in value)
    return value
