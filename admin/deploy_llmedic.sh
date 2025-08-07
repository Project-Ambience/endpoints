#!/bin/bash


set -e

echo "🚀 Deploying LLMedic Services on Gaudi..."
echo "----------------------------------------------"

# --- Variables
COMPOSE_FILE="./docker-compose.yml"
MODEL_DIR="/shared/models"
TMP_DIR="/shared/tmp"
LOG_DIR="/var/log/llmedic"

# --- Step 1: Check for docker-compose.yml
if [ ! -f "$COMPOSE_FILE" ]; then
  echo "❌ Error: docker-compose.yml not found in $(pwd)"
  exit 1
fi

# --- Step 2: Prepare directories
echo "📁 Ensuring shared directories exist..."
mkdir -p "$MODEL_DIR" "$TMP_DIR" "$LOG_DIR"
chown -R $USER:$USER "$MODEL_DIR" "$TMP_DIR" "$LOG_DIR"

# --- Step 3: Clean up stale containers
echo "🧹 Stopping any existing containers..."
docker compose down || true

# --- Step 4: Pull images
echo "📦 Pulling latest images..."
docker compose pull || true

# --- Step 5: Start containers
echo "🐳 Starting LLMedic services..."
docker compose up -d

# --- Step 6: Wait and confirm services
sleep 10
echo "🔍 Checking container status..."
docker ps --filter "name=download_service"
docker ps --filter "name=inference_service"
docker ps --filter "name=finetuning_service"
docker ps --filter "name=prometheus"
docker ps --filter "name=node_exporter"

# Step 9: Set up persistent log collection
echo "🛠 Running log collector setup..."

chmod +x /endpoints/admin/setup_log_services.sh
./endpoints/admin/setup_log_services.sh

# --- Step 7: Start background log collection
echo "📝 Starting container log collection..."

# Kill any previous log collectors to avoid duplicates
pkill -f "docker logs -f .*_service" || true

docker logs -f download_service >> "$LOG_DIR/download.log" 2>&1 &
docker logs -f inference_service >> "$LOG_DIR/inference.log" 2>&1 &
docker logs -f finetuning_service >> "$LOG_DIR/finetune.log" 2>&1 &

echo "----------------------------------------------"
echo "✅ Deployment complete. Logs are being saved to:"
echo "  $LOG_DIR/download.log"
echo "  $LOG_DIR/inference.log"
echo "  $LOG_DIR/finetune.log"

