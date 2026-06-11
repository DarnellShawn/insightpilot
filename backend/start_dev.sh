#!/usr/bin/env bash
# Development launcher. Needed on macOS when .venv lives under an
# iCloud-synced folder (Desktop): macOS 26+ defers loading unsigned
# .so files until they're fully local, which causes ETIMEDOUT on import.
# This script pre-reads every .so so the OS caches them, then starts uvicorn.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Use ~/.venvs/insightpilot (outside iCloud-synced Desktop) to avoid dlopen ETIMEDOUT.
# Fall back to .venv if the external venv doesn't exist.
if [ -d "$HOME/.venvs/insightpilot" ]; then
  VENV="$HOME/.venvs/insightpilot"
else
  VENV="$SCRIPT_DIR/.venv"
fi
PORT="${PORT:-8000}"

echo "==> Pre-warming .so files (macOS iCloud + Gatekeeper cache)…"
find "$VENV" -name "*.so" -print0 | xargs -0 -P8 cat > /dev/null 2>&1 || true
echo "    done ($(find "$VENV" -name "*.so" | wc -l | tr -d ' ') files)"

echo "==> Starting uvicorn on :$PORT"
exec "$VENV/bin/uvicorn" app.main:app --host 0.0.0.0 --port "$PORT" --reload
