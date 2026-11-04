#!/usr/bin/env bash
# Start all four services on Linux or macOS (the counterpart of start-with-ai.bat).
#
#   bash start-all.sh              # all four services
#   bash start-all.sh --no-tryon   # skip CatVTON (no GPU, or just showing the shop)
#   PORT=8080 bash start-all.sh
#
# Every service is independent: if one fails the other three keep serving and the
# site falls back for that feature. Ctrl+C stops everything.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PORT="${PORT:-3000}"
HOST="${HOST:-0.0.0.0}"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
[[ -x "$PY" ]] || PY="$(command -v python3 || command -v python)"

WITH_TRYON=1
WITH_CLIP=1
WITH_FORECAST=1
for arg in "$@"; do
  case "$arg" in
    --no-tryon)    WITH_TRYON=0 ;;
    --no-clip)     WITH_CLIP=0 ;;
    --no-forecast) WITH_FORECAST=0 ;;
    *) echo "unknown flag: $arg"; exit 2 ;;
  esac
done

export HF_HOME="$ROOT/.cache/hf"
export MPLCONFIGDIR="$ROOT/.cache/mpl"
export VISUAL_SEARCH_URL="${VISUAL_SEARCH_URL:-http://127.0.0.1:8001}"
export FORECAST_URL="${FORECAST_URL:-http://127.0.0.1:8002}"
export TRYON_URL="${TRYON_URL:-http://127.0.0.1:8003}"
export PYTORCH_ENABLE_MPS_FALLBACK=1
mkdir -p "$ROOT/.cache/logs"

pids=()
start() {           # start <name> <port> <command...>
  local name="$1" port="$2"; shift 2
  echo "  starting $name on :$port"
  "$@" > "$ROOT/.cache/logs/$name.log" 2>&1 &
  pids+=("$!")
}

cleanup() {
  echo ""
  echo "  stopping ${#pids[@]} service(s) ..."
  for pid in "${pids[@]}"; do kill -TERM "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
  echo "  stopped."
}
trap cleanup INT TERM EXIT

[[ $WITH_CLIP == 1 ]]     && start clip     8001 "$PY" ai-service/visual_search_service.py --port 8001
[[ $WITH_FORECAST == 1 ]] && start forecast 8002 "$PY" ai-service/forecast_service.py   --port 8002
[[ $WITH_TRYON == 1 ]]    && start tryon    8003 "$PY" ai-service/tryon_service.py      --port 8003
start web "$PORT" node server.js

echo ""
echo "  waiting for the AI services to load ..."
for i in $(seq 1 60); do
  ok=0
  curl -sf "http://127.0.0.1:8001/health" >/dev/null 2>&1 && ok=$((ok+1))
  curl -sf "http://127.0.0.1:8002/health" >/dev/null 2>&1 && ok=$((ok+1))
  curl -sf "http://127.0.0.1:8003/health" >/dev/null 2>&1 && ok=$((ok+1))
  [[ $ok -ge 2 ]] && break
  sleep 1
done

echo ""
echo "  ────────────────────────────────────────────"
echo "   SmartMall is up"
echo "   local    http://localhost:$PORT"
if command -v hostname >/dev/null 2>&1; then
  ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  [[ -n "${ip:-}" ]] && echo "   network  http://$ip:$PORT"
fi
echo "   logs     .cache/logs/"
echo "  ────────────────────────────────────────────"
echo "   Ctrl+C to stop everything."
echo ""

# Keep the script alive while the services run.
wait
