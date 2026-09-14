import json
import logging
from typing import Any
from urllib.parse import quote

from upstash_redis import Redis

from config import (
    UPSTASH_REDIS_REST_TOKEN,
    UPSTASH_REDIS_REST_URL,
)


logger = logging.getLogger(__name__)

AVAILABLE_DONATIONS_TTL_SECONDS = 60
AVAILABLE_DONATIONS_VERSION_KEY = (
    "foodshare:donations:available:version"
)


redis_client: Redis | None = None

if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
    redis_client = Redis(
        url=UPSTASH_REDIS_REST_URL,
        token=UPSTASH_REDIS_REST_TOKEN,
    )


def get_cached_json(key: str) -> dict[str, Any] | None:
    if not redis_client:
        return None

    try:
        value = redis_client.get(key)

        if value is None:
            return None

        if isinstance(value, bytes):
            value = value.decode("utf-8")

        if isinstance(value, str):
            return json.loads(value)

        return value

    except Exception:
        logger.warning("Redis cache read failed", exc_info=True)
        return None


def set_cached_json(
    key: str,
    value: dict[str, Any],
    ttl_seconds: int,
) -> None:
    if not redis_client:
        return

    try:
        redis_client.set(
            key,
            json.dumps(value),
            ex=ttl_seconds,
        )
    except Exception:
        logger.warning("Redis cache write failed", exc_info=True)


def get_available_donations_cache_key(
    area: str | None,
    limit: int,
    offset: int,
) -> str:
    version = "0"

    if redis_client:
        try:
            stored_version = redis_client.get(
                AVAILABLE_DONATIONS_VERSION_KEY
            )

            if stored_version is not None:
                version = str(stored_version)

        except Exception:
            logger.warning(
                "Redis cache version read failed",
                exc_info=True,
            )

    normalized_area = (area or "all").strip().casefold()
    encoded_area = quote(normalized_area, safe="")

    return (
        "foodshare:donations:available:"
        f"v{version}:area={encoded_area}:"
        f"limit={limit}:offset={offset}"
    )


def invalidate_available_donations_cache() -> None:
    if not redis_client:
        return

    try:
        redis_client.incr(
            AVAILABLE_DONATIONS_VERSION_KEY
        )
    except Exception:
        logger.warning(
            "Redis cache invalidation failed",
            exc_info=True,
        )