#!/bin/bash
# Unified deploy: LLMedic backend + Project-Ambience/web-demo (prod)
set -euo pipefail

echo "🚀 Deploying LLMedic backend + web-demo (PROD)"
echo "----------------------------------------------"
# ---- Choose docker compose CLI (v2 `docker compose` or legacy `docker-compose`)
if command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  DC="docker compose"
fi

BACKEND_COMPOSE="./docker-compose.yml"
MODEL_DIR="/shared/models"
TMP_DIR="/shared/tmp"
LOG_DIR="/var/log/llmedic"

WEBDEMO_REPO="https://github.com/Project-Ambience/web-demo.git"
WEBDEMO_BRANCH="main"
WEBDEMO_DIR="/opt/web-demo"         
WEBDEMO_ENV_SRC="$WEBDEMO_DIR/.env.prod"
WEBDEMO_ENV_DST="$WEBDEMO_DIR/.env"
WEBDEMO_PROJECT="prod"              
WEBDEMO_API_SERVICE="api"          

need() { command -v "$1" >/dev/null 2>&1 || { echo "❌ Missing dependency: $1"; exit 1; }; }

# ---- Sanity checks
need docker
need git
[ -f "$BACKEND_COMPOSE" ] || { echo "❌ docker-compose.yml not found in $(pwd)"; exit 1; }

# ---- Prepare dirs
echo "📁 Ensuring shared directories exist..."
sudo mkdir -p "$MODEL_DIR" "$TMP_DIR" "$LOG_DIR"
sudo chown -R "$USER:$USER" "$MODEL_DIR" "$TMP_DIR" "$LOG_DIR"

# =======================
# 1) Deploy LLMedic backend (your current repo)
# =======================
echo "🧹 Stopping existing backend containers..."
$DC -f "$BACKEND_COMPOSE" down || true

echo "📦 Pulling latest backend images..."
$DC -f "$BACKEND_COMPOSE" pull || true

echo "🐳 Starting LLMedic backend services..."
$DC -f "$BACKEND_COMPOSE" up -d

sleep 8
echo "🔍 Checking backend container status..."
docker ps --filter "name=download_service"
docker ps --filter "name=inference_service"
docker ps --filter "name=finetuning_service"
docker ps --filter "name=prometheus"
docker ps --filter "name=node_exporter"

# =======================
# 2) Deploy web-demo (frontend + Rails API) using its prod flow (non-interactive)
# =======================
if [ -d "$WEBDEMO_DIR/.git" ]; then
  echo "🔁 Updating web-demo repo at $WEBDEMO_DIR..."
  git -C "$WEBDEMO_DIR" fetch --all --prune
  git -C "$WEBDEMO_DIR" checkout "$WEBDEMO_BRANCH"
  git -C "$WEBDEMO_DIR" pull --ff-only origin "$WEBDEMO_BRANCH"
else
  echo "📥 Cloning $WEBDEMO_REPO into $WEBDEMO_DIR..."
  sudo mkdir -p "$WEBDEMO_DIR"
  sudo chown -R "$USER:$USER" "$WEBDEMO_DIR"
  git clone --branch "$WEBDEMO_BRANCH" "$WEBDEMO_REPO" "$WEBDEMO_DIR"
fi

# Apply prod env
if [ -f "$WEBDEMO_ENV_SRC" ]; then
  echo "🧾 Applying .env.prod -> .env"
  cp "$WEBDEMO_ENV_SRC" "$WEBDEMO_ENV_DST"
else
  echo "⚠️  $WEBDEMO_ENV_SRC not found. Ensure your prod env exists."
fi

# Bring stack down/up (build) under project name "prod"
echo "🛑 Stopping existing web-demo ($WEBDEMO_PROJECT) stack..."
$DC -p "$WEBDEMO_PROJECT" -f "$WEBDEMO_DIR/docker-compose.yml" down || true

echo "🏗️  Building & starting web-demo ($WEBDEMO_PROJECT) stack..."
$DC -p "$WEBDEMO_PROJECT" -f "$WEBDEMO_DIR/docker-compose.yml" up --build -d

# Optional: small wait before migrations (containers need to be up)
sleep 10

# Run Rails migrations in the API container (retry a couple of times)
echo "🗃️  Running Rails DB migrations..."
set +e
for i in 1 2 3; do
  $DC -p "$WEBDEMO_PROJECT" -f "$WEBDEMO_DIR/docker-compose.yml" exec -T "$WEBDEMO_API_SERVICE" bin/rails db:migrate && ok=1 && break
  echo "⏳ api not ready yet, retrying ($i/3)..."
  sleep 8
done
set -e
if [ "${ok:-0}" != "1" ]; then
  echo "❌ Failed to run migrations after retries."
  exit 1
fi

# =======================
# 3) Logs
# =======================
echo "📝 Starting container log collection..."
# Kill previous tails
pkill -f "docker logs -f .*_service" >/dev/null 2>&1 || true
pkill -f "docker logs -f web-demo"   >/dev/null 2>&1 || true
pkill -f "docker logs -f client"     >/dev/null 2>&1 || true
pkill -f "docker logs -f api"        >/dev/null 2>&1 || true

# Backend logs
docker logs -f download_service   >> "$LOG_DIR/download.log"  2>&1 &
docker logs -f inference_service  >> "$LOG_DIR/inference.log" 2>&1 &
docker logs -f finetuning_service >> "$LOG_DIR/finetune.log"  2>&1 &

# Web-demo logs (best effort: try common service names)
for svc in client api web frontend; do
  name="$($DC -p "$WEBDEMO_PROJECT" -f "$WEBDEMO_DIR/docker-compose.yml" ps --services 2>/dev/null | grep -E "^$svc$" || true)"
  if [ -n "$name" ]; then
    cid="$($DC -p "$WEBDEMO_PROJECT" -f "$WEBDEMO_DIR/docker-compose.yml" ps -q "$name" 2>/dev/null || true)"
    if [ -n "$cid" ]; then
      docker logs -f "$cid" >> "$LOG_DIR/${svc}.log" 2>&1 &
      echo "🗒  Tailing $svc → $LOG_DIR/${svc}.log"
    fi
  fi
done

echo "----------------------------------------------"
echo "✅ Deployment complete."
echo "Logs:"
echo "  $LOG_DIR/download.log"
echo "  $LOG_DIR/inference.log"
echo "  $LOG_DIR/finetune.log"
echo "  $LOG_DIR/client.log (if present)"
echo "  $LOG_DIR/api.log (if present)"
echo
echo "ℹ️  web-demo exposes: 7090 (client), 7091 (API) per its compose/env."

