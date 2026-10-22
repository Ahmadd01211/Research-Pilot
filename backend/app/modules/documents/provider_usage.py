"""Content-free provider usage events for operational metering.

Token counts are provider-reported, never estimates of money or billing.
"""

import logging
from typing import Any

logger = logging.getLogger("researchpilot.provider_usage")


def record_usage(operation: str, model: str, status: int, payload: Any) -> None:
    metadata = payload.get("usageMetadata", {}) if isinstance(payload, dict) else {}
    if not isinstance(metadata, dict):
        metadata = {}
    counts = {}
    for name in ("promptTokenCount", "candidatesTokenCount", "totalTokenCount"):
        value = metadata.get(name)
        counts[name] = value if type(value) is int and value >= 0 else None
    logger.warning(
        "provider_usage operation=%s model=%s status=%s prompt_tokens=%s output_tokens=%s total_tokens=%s",
        operation, model, status, counts["promptTokenCount"],
        counts["candidatesTokenCount"], counts["totalTokenCount"],
    )
