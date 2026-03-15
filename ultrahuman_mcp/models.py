#!/usr/bin/env python3
"""
models.py – Pydantic models for Ultrahuman MCP tool inputs.

Created: 2026-03-15
Last updated: 2026-03-15
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GetDailyMetricsInput(BaseModel):
    """Input for ultrahuman_get_daily_metrics."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    email: str = Field(
        ...,
        description="Email of the Ultrahuman user whose data to fetch (must have shared via Partner ID).",
        min_length=3,
        max_length=256,
    )
    date: str = Field(
        ...,
        description="Date in ISO 8601 format YYYY-MM-DD (e.g. 2024-01-15).",
        min_length=10,
        max_length=10,
    )
    response_format: Optional[str] = Field(
        default="markdown",
        description="Output format: 'json' or 'markdown'.",
    )

    @field_validator("email")
    @classmethod
    def email_lower(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("date")
    @classmethod
    def date_iso(cls, v: str) -> str:
        try:
            datetime.strptime(v.strip(), "%Y-%m-%d")
        except ValueError as e:
            raise ValueError("date must be YYYY-MM-DD") from e
        return v.strip()

    @field_validator("response_format")
    @classmethod
    def format_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return "markdown"
        v = (v or "").strip().lower()
        if v not in ("json", "markdown"):
            raise ValueError("response_format must be 'json' or 'markdown'")
        return v


# Metric key for get_live_value: (api type, attribute to read, unit label)
LIVE_METRIC_KEYS = {
    "recovery": ("recovery", "score", "score"),
    "sleep_score": ("sleep", "score", "score"),
    "hrv": ("hrv", "avg", ""),
    "resting_hr": ("night_rhr", "avg", "BPM"),
    "steps": ("steps", "avg", "steps"),
    "recovery_index": ("recovery_index", "value", ""),
    "movement_index": ("movement_index", "value", ""),
    "metabolic_score": ("metabolic_score", "value", ""),
    "vo2_max": ("vo2_max", "value", ""),
    "heart_rate": ("hr", "last_reading", "BPM"),
    "temp": ("temp", "last_reading", "°C"),
}


class GetLiveValueInput(BaseModel):
    """Input for ultrahuman_get_live_value – one metric for substrate/agent context."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    metric: str = Field(
        ...,
        description="Metric to fetch: recovery, sleep_score, hrv, resting_hr, steps, recovery_index, movement_index, metabolic_score, vo2_max, heart_rate, temp.",
        min_length=2,
        max_length=32,
    )
    date: Optional[str] = Field(
        default=None,
        description="Date YYYY-MM-DD. If omitted, uses yesterday (latest available).",
        min_length=10,
        max_length=10,
    )
    email: Optional[str] = Field(
        default=None,
        description="User email. If omitted, uses ULTRAHUMAN_EMAIL from environment.",
        min_length=3,
        max_length=256,
    )

    @field_validator("metric")
    @classmethod
    def metric_lower(cls, v: str) -> str:
        return v.strip().lower().replace(" ", "_")

    @field_validator("date")
    @classmethod
    def date_iso_or_none(cls, v: Optional[str]) -> Optional[str]:
        if not v or not v.strip():
            return None
        try:
            datetime.strptime(v.strip(), "%Y-%m-%d")
        except ValueError as e:
            raise ValueError("date must be YYYY-MM-DD") from e
        return v.strip()

    @field_validator("email")
    @classmethod
    def email_lower_or_none(cls, v: Optional[str]) -> Optional[str]:
        if not v or not v.strip():
            return None
        return v.strip().lower()
