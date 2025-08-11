#!/usr/bin/env bash
set -euo pipefail

# ── Config (override via env)
IMAGE="${IMAGE:-download_service_image}"   # e.g. IMAGE=services or your full image:tag
DISK_PORT="${DISK_PORT:-8010}"
RO_PORT="${RO_PORT:-8011}"
CALLBACK_URL="${CALLBACK_URL:-http://localhost:9999/fake_callback}"

# Models: one big to trigger ENOSPC, one small for quick test
BIG_MODEL="${BIG_MODEL:-bert-base-uncased}"                 # ~400MB+
SMALL_MODEL="${SMALL_MODEL:-sshleifer/tiny-distilroberta-base}"

# How long to watch logs (seconds)
LOG_WAIT="${LOG_WAIT:-25}"

red()   { printf "\e[31m%s\e[0m\n" "$*"; }
green() { printf "\e[32m%s\e[0m\n" "$*"; }
info()  { printf "• %s\n" "$*"; }

require() { command -v "$1" >/dev/null 2>&1 || { red "Missing: $1"; exit 1; }; }
require docker
require curl

run_one_off() {
  local name="$1" port="$2" run_args="$3"
  info "Starting container: $name"
  docker run -d --rm \
    --name "$name" \
    -e HF_HOME=/models \
    -p "${port}:8000" \
    $run_args \
    "$IMAGE" \
    uvicorn download_model:app --host 0.0.0.0 --port 8000 >/dev/null

  # health-ish wait
  for i in {1..30}; do
    if curl -sS -m 1 "http://localhost:${port}/docs" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  red "Service $name did not come up on port $port"
  docker logs "$name" || true
  exit 1
}

post_install() {
  local port="$1" model="$2" id="sysfail-$(date +%s)"
  curl -sS -o /dev/null -w "%{http_code}" \
    -X POST "http://localhost:${port}/models/install" \
    -H "Content-Type: application/json" \
    -d "{\"model_path\":\"${model}\",\"callback_url\":\"${CALLBACK_URL}\",\"id\":\"${id}\"}"
}

# ─────────────────

