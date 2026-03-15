#!/usr/bin/env python3
"""
client.py – HTTP client for Ultrahuman Partner API (Bearer auth, no secrets in logs).

Created: 2026-03-15
Last updated: 2026-03-15
"""

import logging
import os
import re
import time
import uuid
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


def _trace_id() -> str:
    """Short trace ID for request correlation (Watson-style)."""
    return uuid.uuid4().hex[:12]

# Redact email for logs: show first 2 chars + domain
def _redact_email(email: str) -> str:
    if not email or "@" not in email:
        return "<invalid>"
    local, domain = email.rsplit("@", 1)
    if len(local) <= 2:
        mask = "*" * len(local)
    else:
        mask = local[:2] + "*" * (len(local) - 2)
    return f"{mask}@{domain}"


def _sanitize_for_log(text: Optional[str], max_len: int = 20) -> str:
    if not text:
        return ""
    s = str(text).strip()[:max_len]
    return re.sub(r"[\s\r\n]+", " ", s)


def get_config() -> Dict[str, str]:
    """Load config from environment. Never returns token in logs."""
    token = (os.getenv("ULTRAHUMAN_TOKEN") or "").strip()
    email = (os.getenv("ULTRAHUMAN_EMAIL") or "").strip()
    base_url = (os.getenv("ULTRAHUMAN_BASE_URL") or "https://partner.ultrahuman.com").strip().rstrip("/")
    path = (os.getenv("ULTRAHUMAN_API_PATH") or "/api/v1/metrics").strip()
    if not path.startswith("/"):
        path = "/" + path
    return {
        "token": token,
        "email": email,
        "base_url": base_url,
        "api_path": path,
    }


def fetch_daily_metrics(
    email: str,
    date: str,
    *,
    token: Optional[str] = None,
    base_url: Optional[str] = None,
    api_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    GET daily metrics from Ultrahuman Partner API.

    Uses env config for token/base_url/api_path if not passed.
    Raises ValueError if token or email missing; httpx.HTTPStatusError on API errors.
    """
    cfg = get_config()
    token = token or cfg["token"]
    base_url = base_url or cfg["base_url"]
    api_path = api_path or cfg["api_path"]
    url = f"{base_url.rstrip('/')}{api_path}"

    trace_id = _trace_id()
    base_extra: Dict[str, Any] = {
        "trace_id": trace_id,
        "action": "fetch_daily_metrics",
        "email_redacted": _redact_email(email),
        "date": date,
    }

    if not token:
        logger.error(
            "ULTRAHUMAN_TOKEN not set",
            extra={**base_extra, "error_code": "CONFIG_MISSING"},
        )
        raise ValueError("ULTRAHUMAN_TOKEN is not set. Set it in .env or environment.")

    params = {"email": email, "date": date}
    # UltraSignal API expects raw token in Authorization header (no "Bearer " prefix per docs)
    headers = {"Authorization": token, "Accept": "application/json"}

    logger.info(
        "fetch_start",
        extra={**base_extra, "url": url},
    )
    t0 = time.perf_counter()

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        duration_ms = round((time.perf_counter() - t0) * 1000)
        body = _sanitize_for_log(e.response.text if e.response else None, 200)
        logger.error(
            "fetch_error",
            extra={
                **base_extra,
                "duration_ms": duration_ms,
                "status_code": e.response.status_code if e.response else None,
                "response_preview": body,
                "error_code": "HTTP_" + str(e.response.status_code if e.response else "UNKNOWN"),
            },
        )
        if e.response and e.response.status_code == 401:
            raise ValueError(
                "Unauthorized: check ULTRAHUMAN_TOKEN (may be expired or invalid)."
            ) from e
        if e.response and e.response.status_code == 403:
            raise ValueError(
                "Forbidden: this user may not have shared data with your partner (check Partner ID in Ultrahuman app)."
            ) from e
        raise
    except httpx.RequestError as e:
        duration_ms = round((time.perf_counter() - t0) * 1000)
        logger.error(
            "fetch_request_error",
            extra={
                **base_extra,
                "duration_ms": duration_ms,
                "error": str(e),
                "error_code": "REQUEST_ERROR",
            },
        )
        raise ValueError(f"Request failed: {e}") from e

    duration_ms = round((time.perf_counter() - t0) * 1000)
    status = data.get("status")
    err = data.get("error")
    metric_count = len((data.get("data") or {}).get("metric_data") or [])

    # API may return status as "ok" or numeric 200
    if status not in ("ok", 200) or err:
        logger.warning(
            "api_non_ok",
            extra={
                **base_extra,
                "duration_ms": duration_ms,
                "status": status,
                "error": _sanitize_for_log(str(err)),
            },
        )

    logger.info(
        "fetch_success",
        extra={
            **base_extra,
            "duration_ms": duration_ms,
            "metric_count": metric_count,
            "status": status,
        },
    )
    return data
