#!/usr/bin/env bash
# Support Engineer · control panel launcher.
# Starts the stdlib dashboard server, waits until it answers, opens the browser, and
# shuts the server down cleanly on Ctrl+C.
#
# Usage:  ./start_dashboard.sh [PORT]      (default 8787)
set -euo pipefail

HOST="127.0.0.1"
PORT="${1:-8787}"
URL="http://${HOST}:${PORT}/"

# Resolve the repo root from this script's location, so it works from anywhere.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PY="$(command -v python3 || command -v python || true)"
if [[ -z "$PY" ]]; then
  echo "✗ Python no encontrado en el PATH." >&2
  exit 1
fi

# Pick the OS' open command (macOS / Linux / Windows-Git-Bash).
open_browser() {
  if command -v open >/dev/null 2>&1; then open "$1"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$1"
  elif command -v start >/dev/null 2>&1; then start "" "$1"
  else echo "ℹ Abre manualmente: $1"; fi
}

echo "▶ Support Engineer · arrancando panel en ${URL}"
"$PY" dashboard/server.py --host "$HOST" --port "$PORT" &
SERVER_PID=$!

# Stop the server when this script exits (Ctrl+C, error, normal end).
cleanup() { kill "$SERVER_PID" >/dev/null 2>&1 || true; }
trap cleanup EXIT INT TERM

# Wait (up to ~10s) until the server answers before opening the browser.
for _ in $(seq 1 50); do
  if curl -fsS -o /dev/null "$URL" 2>/dev/null; then break; fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "✗ El servidor terminó inesperadamente." >&2; exit 1
  fi
  sleep 0.2
done

echo "✓ Panel listo — abriendo navegador (Ctrl+C para parar)"
open_browser "$URL"

# Keep the server in the foreground so Ctrl+C stops it.
wait "$SERVER_PID"
