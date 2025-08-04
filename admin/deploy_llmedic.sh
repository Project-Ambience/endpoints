#!/bin/bash


set -e

echo "🚀 Deploying LLMedic Platform..."
echo "----------------------------------------------"

# Paths
COMPOSE_FILE="./docker-compose.yml"
LOG_DIR="/var/log/llmedic"
MODEL_DIR="/opt/llmedic/models"
BACKUP_DIR="/opt/llmedic/backups"

# Step 1: Confirm docker-compose file exists
if [ ! -f "$COMPOSE_FILE" ]; then
  echo "❌ Error: docker-compose.yml not found in current directory."
  exit 1
fi

# Step 2: Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p "$LOG_DIR"
mkdir -p "$MODEL_DIR"
mkdir -p "$BACKUP_DIR"

# Step 3: Set permissions
echo "🔒 Setting directory permissions..."
chown -R $USER:$USER "$LOG_DIR" "$MODEL_DIR" "$BACKUP_DIR"

# Step 4: Pull images (optional)
echo "📦 Pulling Docker images (if needed)..."
docker-compose pull

# Step 5: Launch containers
echo "🐳 Starting LLMedic services using Docker Compose..."
docker-compose up -d

# Step 6: Wait for services to initialise
echo "⏳ Waiting briefly for containers to start..."
sleep 10

# Step 7: Check running containers
echo "🔍 Checking status of LLMedic containers..."
docker ps --filter "name=llmedic"


# Step 8: Final summary
echo "----------------------------------------------"
echo "✅ LLMedic deployed successfully!"
echo "• Logs: $LOG_DIR"
echo "• Models: $MODEL_DIR"
echo "• Backups: $BACKUP_DIR"
echo "To view logs: docker logs <container_name>"

