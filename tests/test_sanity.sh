#!/bin/bash
set -e

echo "🚀 Running model download test..."

API_URL="http://localhost:8000/models/install"
MODEL_NAME="sshleifer/tiny-distilroberta-base"
MODEL_ID="test-download-$(date +%s)"
CALLBACK_URL="http://localhost:9999/fake_callback"

CACHE_DIR="$HOME/.cache/huggingface/hub/models--sshleifer--tiny-distilroberta-base"

# 1. Trigger install via API
echo "📡 Sending install request to API..."
curl -s -X POST $API_URL \
  -H "Content-Type: application/json" \
  -d "{\"model_path\": \"$MODEL_NAME\", \"callback_url\": \"$CALLBACK_URL\", \"id\": \"$MODEL_ID\"}"

# 2. Wait for model to download (max 60 seconds)
echo "⏳ Waiting for model to appear at $CACHE_DIR..."
for i in {1..30}; do
  if [ -d "$CACHE_DIR" ]; then
    echo "✅ Model was successfully downloaded!"
    exit 0
  fi
  sleep 2
done

echo "❌ Model not found after waiting. Download may have failed."
exit 1

