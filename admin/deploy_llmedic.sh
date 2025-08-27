
#!/bin/bash
# Unified deploy: LLMedic backend + Project-Ambience/web-demo (dev|prod)
# Usage:
#   ./deploy_all.sh dev
#   ./deploy_all.sh prod
set -euo pipefail

MODE="${1:-dev}"  
echo "🚀 Deploying LLMedic backend + web-demo ($MODE)"
echo "----------------------------------------------"

# ---- Pick compose CLI (v2 or legacy)
if command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  DC="docker compose"
fi

BACKEND_COMPOSE="./docker-compose.yml"
MODEL_DIR="/shared/models"
TMP_DIR="/shared/tmp"
LOG_DIR="/var/log/llmedic"

# ---- web-demo repo settings
WEB_ROOT="/opt"                                 
WEB_DIR="$WEB_ROOT/web-demo"
WEB_REPO_SSH="git@github.com:Project-Ambience/web-demo.git"
WEB_REPO_HTTPS="https://github.com/Project-Ambience/web-demo.git"
WEB_BRANCH="main"

# ---- Dev compose files (from your teammate's script)
DEV_RMQ_COMPOSE="$WEB_DIR/docker-compose.rabbitmq.yml"
DEV_STACK_COMPOSE="$WEB_DIR/docker-compose.dev.yml"
DEV_API_SERVICE="api"                           
DEV_PORTS_INFO="Ports: 5090 (client), 5091 (API)"

# ---- Prod compose + env
PROD_COMPOSE="$WEB_DIR/docker-compose.yml"
PROD_API_SERVICE="api"
PROD_ENV_SRC="$WEB_DIR/.env.prod"
PROD_ENV_DST="$WEB_DIR/.env"
PROD_PROJECT="prod"
PROD_PORTS_INFO="Ports: 7090 (client), 7091 (API)"

need() { command -v "$1" >/dev/null 2>&1 || { echo "❌ Missing dependency: $1"; exit 1; }; }

git_clone_or_update() {
  local dir="$1" ssh_url="$2" https_url="$3" branch="$4"
  if [ -d "$dir/.git" ]; then
    echo "🔁 Updating repo at $dir..."
    git -C "$dir" fetch --all --prune
    git -C "$dir" checkout "$branch"
    git -C "$dir" pull --ff-only origin "$branch"
  else
    echo "📥 Cloning web-demo into $dir..."
    sudo mkdir -p "$dir"
    sudo chown -R "$USER:$USER" "$dir"
    # Prefer SSH; fallback to HTTPS if SSH fails
    if git clone --branch "$branch" "$ssh_url" "$dir"; then
      :
    else
      echo "⚠️  SSH clone failed, trying HTTPS..."
      git clone --branch "$branch" "$https_url" "$dir"
    fi
  fi
}

migrate_with_retries() {
  local compose_file="$1" project_flag="$2" service="$3"
  local tries=5 delay=8
  echo "🗃️  Running DB migrations in service '$service'..."
  set +e
  for i in $(seq 1 "$tries"); do
    $DC $project_flag -f "$compose_file" exec -T "$service" bin/rails db:migrate && { ok=1; break; }
    echo "⏳ $service not ready yet, retrying ($i/$tries)..."
    sleep "$delay"
  done
  set -e
  if [ "${ok:-0}" != "1" ]; then
    echo "❌ Failed to run migrations after $tries attempts."
    exit 1
  fi
}

# ---- Sanity checks
need docker
need git
[ -f "$BACKEND_COMPOSE" ] || { echo "❌ $BACKEND_COMPOSE not found in $(pwd)"; exit 1; }

# ---- Prepare dirs
echo "📁 Ensuring shared directories exist..."
sudo mkdir -p "$MODEL_DIR" "$TMP_DIR" "$LOG_DIR"
sudo chown -R "$USER:$USER" "$MODEL_DIR" "$TMP_DIR" "$LOG_DIR"

# =======================
# 1) Deploy LLMedic backend
# =======================
echo "🧹 Stopping existing backend containers..."
$DC -f "$BACKEND_COMPOSE" down || true

echo "📦 Pulling latest backend images..."
$DC -f "$BACKEND_COMPOSE" pull || true

echo "🐳 Starting LLMedic backend services..."
$DC -f "$BACKEND_COMPOSE" up -d

sleep 8
echo "🔍 Backend status:"
docker ps --filter "name=download_service"
docker ps --filter "name=inference_service"
docker ps --filter "name=finetuning_service"
docker ps --filter "name=prometheus"
docker ps --filter "name=node_exporter"

# =======================
# 2) Deploy web-demo (dev|prod)
# =======================
git_clone_or_update "$WEB_DIR" "$WEB_REPO_SSH" "$WEB_REPO_HTTPS" "$WEB_BRANCH"

if [ "$MODE" = "dev" ]; then
  echo "🧰 DEV: Restarting RabbitMQ stack..."
  [ -f "$DEV_RMQ_COMPOSE" ] || { echo "❌ Missing $DEV_RMQ_COMPOSE"; exit 1; }
  $DC -f "$DEV_RMQ_COMPOSE" down || true
  $DC -f "$DEV_RMQ_COMPOSE" up --build -d

  echo "▶️  DEV: Restarting app stack..."
  [ -f "$DEV_STACK_COMPOSE" ] || { echo "❌ Missing $DEV_STACK_COMPOSE"; exit 1; }
  $DC -f "$DEV_STACK_COMPOSE" down || true
  $DC -f "$DEV_STACK_COMPOSE" up --build -d

  migrate_with_retries "$DEV_STACK_COMPOSE" "" "$DEV_API_SERVICE"
  PORTS_INFO="$DEV_PORTS_INFO"

elif [ "$MODE" = "prod" ]; then
  echo "🧾 PROD: Applying .env.prod → .env (if present)..."
  if [ -f "$PROD_ENV_SRC" ]; then
    cp "$PROD_ENV_SRC" "$PROD_ENV_DST"
  else
    echo "⚠️  $PROD_ENV_SRC not found — continuing without copying."
  fi

  echo "▶️  PROD: Restarting stack..."
  [ -f "$PROD_COMPOSE" ] || { echo "❌ Missing $PROD_COMPOSE"; exit 1; }
  $DC -p "$PROD_PROJECT" -f "$PROD_COMPOSE" down || true
  $DC -p "$PROD_PROJECT" -f "$PROD_COMPOSE" up --build -d

  migrate_with_retries "$PROD_COMPOSE" "-p $PROD_PROJECT" "$PROD_API_SERVICE"
  PORTS_INFO="$PROD_PORTS_INFO"

else
  echo "❌ Unknown mode '$MODE' (use 'dev' or 'prod')"
  exit 1
fi


echo "📝 Starting container log collection..."
pkill -f "docker logs -f .*_service" >/dev/null 2>&1 || true
pkill -f "docker logs -f client"     >/dev/null 2>&1 || true
pkill -f "docker logs -f api"        >/dev/null 2>&1 || true

# Backend logs
docker logs -f download_service   >> "$LOG_DIR/download.log"  2>&1 &
docker logs -f inference_service  >> "$LOG_DIR/inference.log" 2>&1 &
docker logs -f finetuning_service >> "$LOG_DIR/finetune.log"  2>&1 &

for svc in client api; do
  if [ "$MODE" = "dev" ]; then
    sid="$($DC -f "${DEV_STACK_COMPOSE}" ps -q "$svc" 2>/dev/null || true)"
  else
    sid="$($DC -p "$PROD_PROJECT" -f "${PROD_COMPOSE}" ps -q "$svc" 2>/dev/null || true)"
  fi
  if [ -n "$sid" ]; then
    docker logs -f "$sid" >> "$LOG_DIR/${svc}.log" 2>&1 &
    echo "🗒  Tailing $svc → $LOG_DIR/${svc}.log"
  fi
done

echo "----------------------------------------------"
echo "✅ Deployment complete ($MODE). $PORTS_INFO"
echo "Logs:"
echo "  $LOG_DIR/download.log"
echo "  $LOG_DIR/inference.log"
echo "  $LOG_DIR/finetune.log"
echo "  $LOG_DIR/client.log (if present)"
echo "  $LOG_DIR/api.log (if present)"
