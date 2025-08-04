#!/bin/bash

# ==============================================
# LLMedic Gaudi-Compatible Deployment Script
# Author: Your Name
# Description:
#   Deploys the LLMedic endpoint stack using your
#   provided docker-compose.yml. Assumes a shared
#   /shared/models and /shared/tmp.
# ==============================================

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
mkdir -p "$MODEL_DIR"
mkdir -p "$TMP_DIR"
mkdir -p "$LOG_DIR"

echo "🔒 Setting permissions..."
chown -R $USER:$USER "$MODEL_DIR" "$TMP_DIR" "$LOG_DIR"

# --- Step 3: Clean up stale containers
echo "🧹 Cleaning up any stale containers..."
docker compose down || true

# --- Step 4: Pull or rebuild images
echo "📦 Ensuring latest images are available..."
docker compose pull || true

# --- Step 5: Start services
echo "🐳 Starting services using Docker Compose..."
docker compose up -d

# --- Step 6: Wait and check container status
sleep 10
echo "🔍 Verifying LLMedic container status..."
docker ps --filter "name=download_service"
docker ps --filter "name=inference_service"
docker ps --filter "name=finetuning_service"

# --- Step 7: Final Summary
echo "----------------------------------------------"
echo "✅ LLMedic deployed successfully on Gaudi!"
echo "• Models dir: $MODEL_DIR"
echo "• Temp dir: $TMP_DIR"
echo "• Logs dir:  $LOG_DIR"
echo "To interact with a container: docker exec -it <container_name> bash"

