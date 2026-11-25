"""Content-free provider usage events for operational metering.

Token counts are provider-reported, never estimates of money or billing.
"""

import logging
from typing import Any

logger = logging.getLogger("researchpilot.provider_usage")


def record_usage(operation: str, model: str, status: int, payload: Any) -> None:
    payload = payload if isinstance(payload, dict) else {}
    google = payload.get("usageMetadata")
    openai_style = payload.get("usage")  # OpenRouter reports OpenAI-compatible usage.
    names = {
        "promptTokenCount": "prompt_tokens",
        "candidatesTokenCount": "completion_tokens",
        "totalTokenCount": "total_tokens",
    }
    counts = {}
    for name, alternate in names.items():
        value = (
            google.get(name) if isinstance(google, dict)
            else openai_style.get(alternate) if isinstance(openai_style, dict)
            else None
        )
        counts[name] = value if type(value) is int and value >= 0 else None
    logger.warning(
        "provider_usage operation=%s model=%s status=%s prompt_tokens=%s output_tokens=%s total_tokens=%s",
        operation, model, status, counts["promptTokenCount"],
        counts["candidatesTokenCount"], counts["totalTokenCount"],
    )
