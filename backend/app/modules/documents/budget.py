"""Server-enforced daily answer budget for one provider key, with a per-user share.

Free provider tiers limit requests per key per day. A slot is reserved atomically
immediately before each provider call and never refunded: a failed request may
still count against the provider's quota, so refunds could overrun it. The global
and per-user counters are checked and incremented in one script, so a refused
attempt reserves nothing.
"""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from redis import Redis

from app.core.config import Settings
from app.core.security import hash_token

RESERVE_SCRIPT = """
local total = tonumber(redis.call('GET', KEYS[1]) or '0')
if total >= tonumber(ARGV[1]) then return -1 end
local mine = tonumber(redis.call('GET', KEYS[2]) or '0')
if mine >= tonumber(ARGV[2]) then return -2 end
redis.call('INCR', KEYS[1])
redis.call('INCR', KEYS[2])
redis.call('EXPIRE', KEYS[1], 172800)
redis.call('EXPIRE', KEYS[2], 172800)
return 1
"""


def _prefix(settings: Settings) -> str:
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"{settings.rate_namespace}:answer-budget:{settings.answer_provider}:{day}"


def _seconds_until_reset() -> int:
    now = datetime.now(UTC)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((tomorrow - now).total_seconds()))


def remaining(redis: Redis, settings: Settings) -> int:
    used = redis.get(_prefix(settings))
    return max(0, settings.answer_daily_limit - int(used or 0))  # type: ignore[arg-type]


def reserve(redis: Redis, settings: Settings, user: str) -> None:
    prefix = _prefix(settings)
    result = int(redis.eval(  # type: ignore[arg-type]
        RESERVE_SCRIPT, 2, prefix, f"{prefix}:user:{hash_token(user)}",
        str(settings.answer_daily_limit), str(settings.answer_user_limit),
    ))
    if result > 0:
        return
    headers = {"Retry-After": str(_seconds_until_reset())}
    if result == -1:
        raise HTTPException(
            429,
            "The shared daily research-answer limit has been reached. Evidence search still "
            "works; answers reset at 00:00 UTC.",
            headers=headers,
        )
    raise HTTPException(
        429,
        "You have used your daily share of research answers. Evidence search still works; "
        "answers reset at 00:00 UTC.",
        headers=headers,
    )
