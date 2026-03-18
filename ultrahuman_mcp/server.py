#!/usr/bin/env python3
"""
server.py – FastMCP server for Ultrahuman Partner API (daily metrics tool).

Created: 2026-03-15
Last updated: 2026-03-18
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from mcp.server.fastmcp import FastMCP

from .client import fetch_daily_metrics
from .models import GetDailyMetricsInput, GetLiveValueInput, LIVE_METRIC_KEYS


def _redact_email(email: str) -> str:
    if not email or "@" not in email:
        return "*"
    local, _, domain = email.partition("@")
    return (local[:2] if len(local) >= 2 else local) + "*@" + domain

logger = logging.getLogger(__name__)


def _trace_id() -> str:
    return uuid.uuid4().hex[:12]


def _compute_steps_total(obj: Dict[str, Any]) -> Optional[int]:
    """
    Ultrahuman `steps` usually contains a `values` time-series plus an `avg`.
    For user-facing "steps for the day", a total is more meaningful than an average-per-bucket.

    Heuristic:
    - If `values` is mostly non-decreasing (cumulative), use the last value.
    - Else treat `values` as per-bucket increments and sum them.
    - Fallback to `avg` if `values` missing/unusable.
    """
    values = obj.get("values")
    if isinstance(values, list) and values:
        nums: List[float] = []
        for it in values:
            if isinstance(it, dict) and "value" in it:
                v = it.get("value")
            else:
                v = it
            if isinstance(v, (int, float)):
                nums.append(float(v))
        if len(nums) >= 2:
            non_decreasing = sum(1 for a, b in zip(nums, nums[1:]) if b >= a)
            if non_decreasing / max(1, (len(nums) - 1)) >= 0.8:
                return int(round(nums[-1]))
        if nums:
            return int(round(sum(nums)))

    avg = obj.get("avg")
    if isinstance(avg, (int, float)):
        return int(round(avg))
    return None


def _pluck_live_value(data: Dict[str, Any], metric_key: str) -> Optional[Tuple[Any, str]]:
    """From daily API response, pluck value and unit for one metric. Returns (value, unit) or None."""
    info = LIVE_METRIC_KEYS.get(metric_key)
    if not info:
        return None
    api_type, attr, unit = info
    inner = data.get("data") or {}
    for m in (inner.get("metric_data") or []):
        if (m.get("type") or "") == api_type:
            obj = m.get("object") or {}
            if api_type == "steps":
                steps_total = _compute_steps_total(obj)
                if steps_total is not None:
                    return (steps_total, unit or "steps")
            val = obj.get(attr)
            if val is not None:
                return (val, unit or "")
    return None


mcp = FastMCP("ultrahuman_mcp")


def _format_daily_metrics_markdown(data: Dict[str, Any]) -> str:
    """Build a short human-readable Markdown summary from API response (matches official Response.json structure)."""
    inner = data.get("data") or {}
    metrics: List[Dict[str, Any]] = inner.get("metric_data") or []
    if not metrics:
        err = data.get("error")
        if err:
            return f"No metric data for this date. API message: {err}"
        return "No metric data available for this date."

    lines = ["## Daily metrics summary\n"]
    for m in metrics:
        typ = m.get("type") or ""
        obj = m.get("object") or {}
        title = obj.get("title") or typ.replace("_", " ").title()
        if typ == "sleep":
            score = obj.get("score")
            details = obj.get("details") or {}
            quick = details.get("quick_metrics") or []
            lines.append(f"### Sleep (score: {score}/10)" if score is not None else "### Sleep")
            for q in quick[:4]:
                disp = q.get("display_text") or str(q.get("value", ""))
                lines.append(f"- **{q.get('title', '')}:** {disp}")
            summary_list = details.get("summary") or []
            if summary_list:
                lines.append("**Summary:** " + ", ".join(f"{s.get('title', '')} ({s.get('state_title', '')})" for s in summary_list[:5]))
            insights = details.get("insights") or []
            for ins in insights[:2]:
                lines.append(f"- *{ins.get('title', '')}* — {ins.get('description', '')}")
        elif typ == "recovery":
            score = obj.get("score")
            lines.append(f"### Recovery — {title}: **{score}/10**" if score is not None else f"### Recovery — {title}")
        elif typ in ("hr", "night_rhr"):
            last = obj.get("last_reading") or obj.get("avg")
            unit = obj.get("unit") or "BPM"
            lines.append(f"### {title}: **{last} {unit}**")
        elif typ == "hrv":
            avg = obj.get("avg")
            lines.append(f"### HRV — {title}: **{avg}** (avg)" if avg is not None else f"### HRV — {title}")
        elif typ == "steps":
            total = _compute_steps_total(obj)
            lines.append(f"### Steps: **{int(total)}**" if total is not None else "### Steps")
        elif typ == "motion":
            avg = obj.get("avg")
            lines.append(f"### Motion: **{avg:.0f}** (avg)" if avg is not None else "### Motion")
        elif typ == "temp":
            last = obj.get("last_reading")
            unit = obj.get("unit") or "°C"
            lines.append(f"### {title}: **{last} {unit}**" if last is not None else f"### {title}")
        elif typ in ("metabolic_score", "recovery_index", "movement_index", "vo2_max",
                    "glucose_variability", "average_glucose", "hba1c", "time_in_target"):
            val = obj.get("value")
            if val is not None:
                lines.append(f"### {title}: **{val}**")
    return "\n".join(lines)


@mcp.tool(
    name="ultrahuman_get_daily_metrics",
    annotations={
        "title": "Get Ultrahuman daily metrics",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ultrahuman_get_daily_metrics(params: GetDailyMetricsInput) -> str:
    """Fetch daily bio metrics from Ultrahuman (sleep, recovery, HR, HRV, steps, glucose, etc.) for a given user and date.

    Use this when the user asks for sleep, recovery, readiness, daily metrics, morning brief, ring data, or glucose/metabolic data for a specific date. Requires the user's Ultrahuman account email and date in YYYY-MM-DD.

    Args:
        params: email (Ultrahuman user), date (YYYY-MM-DD), optional response_format ('json' or 'markdown').

    Returns:
        str: Metric summary as Markdown (default) or raw JSON. Includes sleep score, recovery, HR, HRV, steps, and if available glucose/metabolic metrics.
    """
    trace_id = _trace_id()
    tool_extra = {"trace_id": trace_id, "tool": "ultrahuman_get_daily_metrics", "date": params.date}
    logger.info("tool_invoke_start", extra={**tool_extra, "email_redacted": _redact_email(params.email)})
    t0 = time.perf_counter()
    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None,
            lambda: fetch_daily_metrics(params.email, params.date),
        )
    except ValueError as e:
        duration_ms = round((time.perf_counter() - t0) * 1000)
        logger.warning("tool_value_error", extra={**tool_extra, "duration_ms": duration_ms, "message": str(e), "error_code": "VALUE_ERROR"})
        return f"Error: {e}"
    except Exception as e:
        duration_ms = round((time.perf_counter() - t0) * 1000)
        logger.exception("tool_error", extra={**tool_extra, "duration_ms": duration_ms, "error_type": type(e).__name__, "error_code": "TOOL_ERROR"})
        return f"Error: {type(e).__name__}: {e}"

    duration_ms = round((time.perf_counter() - t0) * 1000)
    logger.info("tool_invoke_success", extra={**tool_extra, "duration_ms": duration_ms})
    fmt = (params.response_format or "").strip().lower() or "markdown"
    if fmt == "json":
        return json.dumps(data, indent=2)
    return _format_daily_metrics_markdown(data)


@mcp.tool(
    name="ultrahuman_get_live_value",
    annotations={
        "title": "Get one live metric value (for substrate/agent context)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ultrahuman_get_live_value(params: GetLiveValueInput) -> str:
    """Fetch a single metric value (e.g. recovery, sleep_score, hrv) for the given or latest date. Returns compact JSON so the substrate can send it with every message to the agent.

    Use this when you need one number to attach to the agent context (e.g. latest recovery score, last night's sleep score). Metric: recovery, sleep_score, hrv, resting_hr, steps, recovery_index, movement_index, metabolic_score, vo2_max, heart_rate, temp.

    Args:
        params: metric (required), date (optional, default yesterday), email (optional, default from env).

    Returns:
        str: JSON object with metric, value, date, unit, source (e.g. {\"metric\": \"recovery\", \"value\": 7, \"date\": \"2026-03-14\", \"unit\": \"score\", \"source\": \"ultrahuman\"}).
    """
    trace_id = _trace_id()
    email = (params.email or os.getenv("ULTRAHUMAN_EMAIL") or "").strip()
    if not email:
        return json.dumps({"error": "email_required", "message": "Set email or ULTRAHUMAN_EMAIL."})
    date = params.date
    if not date:
        date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    tool_extra = {"trace_id": trace_id, "tool": "ultrahuman_get_live_value", "metric": params.metric, "date": date}
    logger.info("tool_invoke_start", extra={**tool_extra, "email_redacted": _redact_email(email)})
    t0 = time.perf_counter()
    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: fetch_daily_metrics(email, date))
    except ValueError as e:
        duration_ms = round((time.perf_counter() - t0) * 1000)
        logger.warning("tool_value_error", extra={**tool_extra, "duration_ms": duration_ms, "message": str(e), "error_code": "VALUE_ERROR"})
        return json.dumps({"error": "fetch_failed", "message": str(e), "metric": params.metric, "date": date})
    except Exception as e:
        duration_ms = round((time.perf_counter() - t0) * 1000)
        logger.exception("tool_error", extra={**tool_extra, "duration_ms": duration_ms, "error_type": type(e).__name__, "error_code": "TOOL_ERROR"})
        return json.dumps({"error": "fetch_failed", "message": str(e), "metric": params.metric, "date": date})
    out = _pluck_live_value(data, params.metric)
    duration_ms = round((time.perf_counter() - t0) * 1000)
    if out is None:
        logger.info("tool_live_value_missing", extra={**tool_extra, "duration_ms": duration_ms})
        return json.dumps({
            "metric": params.metric,
            "value": None,
            "date": date,
            "unit": "",
            "source": "ultrahuman",
            "message": "Metric not found or no data for this date.",
        })
    value, unit = out
    payload = {
        "metric": params.metric,
        "value": value,
        "date": date,
        "unit": unit or ("score" if "score" in params.metric or params.metric == "recovery" else ""),
        "source": "ultrahuman",
    }
    logger.info("tool_invoke_success", extra={**tool_extra, "duration_ms": duration_ms, "value": value})
    return json.dumps(payload)


