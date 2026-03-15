#!/usr/bin/env bash
# File: run_mcp.sh
# Description: Run Ultrahuman MCP server via stdio (for Cursor / MCP clients).
# Created: 2026-03-16
# Last updated: 2026-03-16

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

# Load .env if present (no override of existing env)
if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.env"
  set +a
fi

# Prefer venv in project root so MCP deps are used
if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  exec "$ROOT_DIR/.venv/bin/python" -m ultrahuman_mcp
fi
exec python3 -m ultrahuman_mcp
