---
title: api_summary.md
description: Short reference for Ultrahuman Partner API (auth, params, response).
created: 2026-03-16
updated: 2026-03-18
---

# Ultrahuman Partner API – Summary

Quick reference for the Ultrahuman Partner (UltraSignal) API used by this MCP. Full docs: [UltraSignal API Documentation](https://ultrahumanapp.notion.site/UltraSignal-API-Documentation-5f32ec15ef6b4fa5bc8249f7b875d212).

## Base URL and auth

- **Base URL:** `https://partner.ultrahuman.com` (configurable via `ULTRAHUMAN_BASE_URL`).
- **Path:** `/api/v1/metrics` (configurable via `ULTRAHUMAN_API_PATH`). Per [UltraSignal API Documentation](https://ultrahumanapp.notion.site/API-Documentation-5f32ec15ef6b4fa5bc8249f7b875d212): Live environment = `https://partner.ultrahuman.com/api/v1/metrics`.
- **Auth:** Header `Authorization: <token>` (raw token only; **no** "Bearer " prefix). Token from partner onboarding. Example: `curl ... --header 'Authorization: YOUR_TOKEN'`.

## Request

- **Method:** GET.
- **Query (or body) parameters:**
  - `email` (string): Email of the user whose data to fetch. User must have shared data with your partner (e.g. via Partner ID in the Ultrahuman app).
  - `date` (string): Date in ISO 8601 format **YYYY-MM-DD** (e.g. `2024-01-15`).

## Response

- **Top-level:** `status` ("ok" | error), optional `error`, and `data`.
- **`data.metric_data`:** Array of metric objects. Each has:
  - `type`: string (see table below).
  - `object`: metric payload (scores, values, details). Often includes `day_start_timestamp`, `title`, and type-specific fields.

Full example: [Response.json](https://ultrahumanapp.notion.site/Response-json-ae7c2ae1e8ca4a07b4a254d71c89b558) in the official docs.

### Sleep object (type: `sleep`)

- `score` (0–10), `title` ("Sleep Score"), `is_processing_new_data`.
- **`details`**:
  - **`quick_metrics`**: array of `{ title, display_text, unit, value, type }` (e.g. TOTAL SLEEP "7h 5m", SLEEP EFFICIENCY "93%", AVG HEART RATE, AVG HRV).
  - **`sleep_stages`**: array of `{ title, type, percentage }` (deep_sleep, light_sleep, rem_sleep, awake).
  - **`summary`**: array of `{ title, state, state_title, score }` (e.g. Sleep Efficiency "optimal", HRV Form "warning").
  - **`insights`**: array of `{ title, description }` (e.g. "Optimal heart rate", "Improve REM for better memory").
  - **`sleep_graph`**, **`movement_graph`**, **`hr_graph`**, **`hrv_graph`**: time-series data (start/end or timestamp + value/type).
  - **`bedtime_start`**, **`bedtime_end`**: Unix timestamps.

### Other metric objects

- **hr / temp**: `values` (array of `{ value, timestamp }`), `last_reading`, `unit`.
- **hrv / steps / motion / night_rhr**: `values`, `avg` (and for night_rhr: `title` "Resting HR").
- **recovery**: `score` (0–10), `title` "Recovery Score".
- **glucose**: `values` array of `{ timestamp, value }` (mg/dL).
- **metabolic_score, glucose_variability, average_glucose, hba1c, time_in_target, recovery_index, movement_index, vo2_max**: `value` (number), `title`.

### Common metric types (quick reference)

| type | object contents (typical) |
|------|---------------------------|
| sleep | score, details (quick_metrics, sleep_stages, summary, insights) |
| recovery | score |
| hr | values, last_reading, unit (BPM) |
| night_rhr | values, avg, title "Resting HR" |
| hrv | values, avg, subtitle "Average" |
| steps | values, avg |
| motion | values, avg |
| temp | values, last_reading, unit (°C) |
| glucose | values (timestamp, value) |
| metabolic_score | value |
| glucose_variability | value (%) |
| average_glucose | value (mg/dL) |
| hba1c | value |
| time_in_target | value (%) |
| recovery_index | value |
| movement_index | value |
| vo2_max | value |

Use this summary when writing skills or tools that interpret or display Ultrahuman data.

## Note on "steps" (avg vs total)

The API provides `steps.object.values` and `steps.object.avg`. In practice, `avg` may be an average-per-bucket value and can look misleadingly low for "steps today".
For user-facing displays, prefer computing a **daily total** from `values` (cumulative last value, or sum of increments) with `avg` only as a fallback.

## Live value (for substrate / agent context)

The MCP tool **ultrahuman_get_live_value** returns a single metric value as compact JSON so the substrate can attach it to every message to the agent. It uses the same daily API; `date` defaults to yesterday. Supported metrics: `recovery`, `sleep_score`, `hrv`, `resting_hr`, `steps`, `recovery_index`, `movement_index`, `metabolic_score`, `vo2_max`, `heart_rate`, `temp`. Response shape: `{"metric", "value", "date", "unit", "source": "ultrahuman"}`.
