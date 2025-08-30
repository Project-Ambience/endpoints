#!/usr/bin/env bash
# Unified deploy: LLMedic backend + Project-Ambience/web-demo (dev|prod)
# Usage:
#   ./admin/deploy_llmedic.sh dev [--rebuild] [--no-logs]
#   ./admin/deploy_llmedic.sh prod [--rebuild] [--no-logs]

set -euo pipefail

MODE="${1:-dev}"   # dev | prod
shift || true

REBUILD=0
TAIL_LOGS=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --rebuild) REBUILD=1; shift ;;
    --no-logs) TAIL_LOGS=0; shift ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

echo "🚀 Deploying LLMedic backend + web-demo ($MODE)"
echo "----------------------------------------------"

# --- Pick compose CLI (v2 or legacy)
if command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  DC="docker compose"
fi

need() { command -v "$1" >/dev/null 2>&1 || { echo "❌ Missing dependency: $1"; exit 1; }; }

# --- Resolve paths relative to this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- Backend (current repo)
BACKEND_COMPOSE="$REPO_ROOT/docker-compose.yml"
MODEL_DIR="/shared/models"
TMP_DIR="/shared/tmp"
LOG_DIR="/var/log/llmedic"

# --- web-demo repo settings
WEB_DIR="${WEB_DIR:-$HOME/web-demo}"
WEB_REPO_SSH="git@github.com:Project-Ambience/web-demo.git"
WEB_REPO_HTTPS="https://github.com/Project-Ambience/web-demo.git"
WEB_BRANCH="main"

# --- DEV compose files
DEV_RMQ_COMPOSE="$WEB_DIR/docker-compose.rabbitmq.yml"
DEV_STACK_COMPOSE="$WEB_DIR/docker-compose.dev.yml"
DEV_API_SERVICE="api"
DEV_RMQ_SERVICE="rabbitmq"
DEV_PORTS_INFO="Ports: 5090 (client), 5091 (API)"

# --- PROD compose files
PROD_COMPOSE="$WEB_DIR/docker-compose.yml"
PROD_API_SERVICE="api"
PROD_RMQ_SERVICE="rabbitmq"
PROD_ENV_SRC="$WEB_DIR/.env.prod"
PROD_ENV_DST="$WEB_DIR/.env"
PROD_PROJECT="prod"
PROD_PORTS_INFO="Ports: 7090 (client), 7091 (API)"

git_clone_or_update() {
  local dir="$1" ssh_url="$2" https_url="$3" branch="$4"
  if [ -d "$dir/.git" ]; then
    echo "🔁 Updating repo at $dir..."
    git -C "$dir" fetch --all --prune
    git -C "$dir" checkout "$branch"
    git -C "$dir" pull --ff-only origin "$branch"
  else
    echo "📥 Cloning web-demo into $dir..."
    mkdir -p "$dir"
    if git clone --branch "$branch" "$ssh_url" "$dir"; then :; else
      echo "⚠️  SSH clone failed, trying HTTPS..."
      git clone --branch "$branch" "$https_url" "$dir"
    fi
  fi
}

wait_for_healthy() {
  # args: <compose-file> <service-name> [proj args...]
  local compose_file="$1"; shift
  local service="$1"; shift
  local proj_args=("$@")
  echo "⏳ Waiting for '$service' to be healthy..."
  local cid
  cid="$($DC "${proj_args[@]}" -f "$compose_file" ps -q "$service" 2>/dev/null || true)"
  if [ -z "$cid" ]; then
    echo "❌ Cannot find container for $service"; exit 1
  fi
  local has_health
  has_health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$cid" || true)"
  local start="$(date +%s)"
  local timeout=180
  if [ -z "$has_health" ]; then
    while ! (timeout 1 bash -lc "</dev/tcp/127.0.0.1/5672") 2>/dev/null; do
      sleep 2
      if (( $(date +%s) - start > timeout )); then
        echo "⚠️  Timed out waiting for RabbitMQ port; proceeding anyway."
        break
      fi
    done
    return 0
  fi
  while true; do
    local status
    status="$(docker inspect -f '{{.State.Health.Status}}' "$cid" || true)"
    if [ "$status" = "healthy" ]; then
      echo "✅ $service is healthy."
      break
    fi
    if (( $(date +%s) - start > timeout )); then
      echo "⚠️  Timed out waiting for $service to be healthy; proceeding."
      break
    fi
    sleep 2
  done
}

migrate_with_retries() {
  local compose_file="$1" project_flag="$2" service="$3"
  local tries=5 delay=8 ok=0
  echo "🗃️  Running DB migrations in service '$service'..."
  set +e
  for i in $(seq 1 "$tries"); do
    $DC $project_flag -f "$compose_file" exec -T "$service" bin/rails db:migrate && { ok=1; break; }
    echo "⏳ $service not ready yet, retrying ($i/$tries)..."
    sleep "$delay"
  done
  set -e
  [ "$ok" -eq 1 ] || { echo "❌ Failed to run migrations after $tries attempts."; exit 1; }
}

# --- Sanity checks
need docker
need git
[ -f "$BACKEND_COMPOSE" ] || { echo "❌ $BACKEND_COMPOSE not found"; exit 1; }

# --- Prepare dirs
echo "📁 Ensuring shared directories exist..."
sudo mkdir -p "$MODEL_DIR" "$TMP_DIR" "$LOG_DIR"
sudo chown -R "$USER:$USER" "$MODEL_DIR" "$TMP_DIR" "$LOG_DIR"

# 0) Get/refresh web-demo
git_clone_or_update "$WEB_DIR" "$WEB_REPO_SSH" "$WEB_REPO_HTTPS" "$WEB_BRANCH"

# 1) Start RabbitMQ FIRST
if [ "$MODE" = "dev" ]; then
  [ -f "$DEV_RMQ_COMPOSE" ] || { echo "❌ Missing $DEV_RMQ_COMPOSE"; exit 1; }
  echo "🐇 Starting RabbitMQ (DEV)..."
  if [ "$REBUILD" -eq 1 ]; then
    $DC -f "$DEV_RMQ_COMPOSE" up --build -d
  else
    $DC -f "$DEV_RMQ_COMPOSE" up -d
  fi
  wait_for_healthy "$DEV_RMQ_COMPOSE" "$DEV_RMQ_SERVICE"
elif [ "$MODE" = "prod" ]; then
  echo "🧾 PROD: Applying .env.prod → .env (if present)..."
  if [ -f "$PROD_ENV_SRC" ]; then cp "$PROD_ENV_SRC" "$PROD_ENV_DST"; else echo "⚠️  $PROD_ENV_SRC not found — continuing."; fi
  [ -f "$PROD_COMPOSE" ] || { echo "❌ Missing $PROD_COMPOSE"; exit 1; }
  echo "🐇 Starting RabbitMQ (PROD stack)..."
  if [ "$REBUILD" -eq 1 ]; then
    $DC -p "$PROD_PROJECT" -f "$PROD_COMPOSE" up --build -d
  else
    $DC -p "$PROD_PROJECT" -f "$PROD_COMPOSE" up -d
  fi
  wait_for_healthy "$PROD_COMPOSE" "$PROD_RMQ_SERVICE" -p "$PROD_PROJECT"
else
  echo "❌ Unknown mode '$MODE' (use 'dev' or 'prod')"; exit 1
fi

# 2) Start LLMedic backend (after RMQ)
echo "🐳 Starting LLMedic backend services..."
if [ "$REBUILD" -eq 1 ]; then
  $DC -f "$BACKEND_COMPOSE" up --build -d --remove-orphans
else
  $DC -f "$BACKEND_COMPOSE" up -d --remove-orphans
fi

sleep 6
echo "🔍 Backend status:"
docker ps --filter "name=download_service"
docker ps --filter "name=inference_service"
docker ps --filter "name=finetuning_service"
docker ps --filter "name=prometheus"
docker ps --filter "name=node_exporter"

# 3) Start app stack & migrate
if [ "$MODE" = "dev" ]; then
  echo "▶️  DEV: Starting app stack (no RMQ bounce)..."
  [ -f "$DEV_STACK_COMPOSE" ] || { echo "❌ Missing $DEV_STACK_COMPOSE"; exit 1; }
  if [ "$REBUILD" -eq 1 ]; then
    $DC -f "$DEV_STACK_COMPOSE" up --build -d
  else
    $DC -f "$DEV_STACK_COMPOSE" up -d
  fi
  migrate_with_retries "$DEV_STACK_COMPOSE" "" "$DEV_API_SERVICE"
  PORTS_INFO="$DEV_PORTS_INFO"
else
  echo "▶️  PROD: Stack already up; running migrations..."
  migrate_with_retries "$PROD_COMPOSE" "-p $PROD_PROJECT" "$PROD_API_SERVICE"
  PORTS_INFO="$PROD_PORTS_INFO"
fi

# 4) Logs (optional tails)
if [ "$TAIL_LOGS" -eq 1 ]; then
  echo "📝 Starting container log collection..."
  pkill -f "docker logs -f .*_service" >/dev/null 2>&1 || true
  pkill -f "docker logs -f client"     >/dev/null 2>&1 || true
  pkill -f "docker logs -f api"        >/dev/null 2>&1 || true

  docker logs -f download_service   >> "$LOG_DIR/download.log"  2>&1 &
  docker logs -f inference_service  >> "$LOG_DIR/inference.log" 2>&1 &
  docker logs -f finetuning_service >> "$LOG_DIR/finetune.log"  2>&1 &

  if [ "$MODE" = "dev" ]; then
    sid_client="$($DC -f "$DEV_STACK_COMPOSE" ps -q client 2>/dev/null || true)"
    sid_api="$($DC -f "$DEV_STACK_COMPOSE" ps -q api 2>/dev/null || true)"
  else
    sid_client="$($DC -p "$PROD_PROJECT" -f "$PROD_COMPOSE" ps -q client 2>/dev/null || true)"
    sid_api="$($DC -p "$PROD_PROJECT" -f "$PROD_COMPOSE" ps -q api 2>/dev/null || true)"
  fi
  [ -n "${sid_client:-}" ] && docker logs -f "$sid_client" >> "$LOG_DIR/client.log" 2>&1 & && echo "🗒  Tailing client → $LOG_DIR/client.log" || true
  [ -n "${sid_api:-}" ]    && docker logs -f "$sid_api"    >> "$LOG_DIR/api.log"    2>&1 & && echo "🗒  Tailing api → $LOG_DIR/api.log"       || true
fi

echo "----------------------------------------------"
echo "✅ Deployment complete ($MODE). $PORTS_INFO"
echo "Logs:"
echo "  $LOG_DIR/download.log"
echo "  $LOG_DIR/inference.log"
echo "  $LOG_DIR/finetune.log"
echo "  $LOG_DIR/client.log (if present)"
echo "  $LOG_DIR/api.log (if present)"

