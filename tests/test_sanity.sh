#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Running model download test..."

API_URL="${API_URL:-http://localhost:8000/models/install}"
MODEL_NAME="${MODEL_NAME:-sshleifer/tiny-distilroberta-base}"
MODEL_ID="test-download-$(date +%s)"
CALLBACK_URL="${CALLBACK_URL:-http://localhost:9999/fake_callback}"

# If your FastAPI is in Docker, set CONTAINER to the container name to check cache inside it.
CONTAINER="${CONTAINER:-}"   # e.g., CONTAINER=inference_service

# Hugging Face cache root. If HF_HOME is set, use that; otherwise check common defaults
HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
CANDIDATE_DIRS=(
  "$HF_HOME/hub/models--${MODEL_NAME//\//--}"
  "$HOME/.cache/huggingface/hub/models--${MODEL_NAME//\//--}"
  "/root/.cache/huggingface/hub/models--${MODEL_NAME//\//--}"
)

# 1) Trigger install via API and capture HTTP status
echo "📡 Sending install request to API: $API_URL"
HTTP_CODE=$(curl -sS -m 10 -o /dev/null -w "%{http_code}" -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"model_path\": \"$MODEL_NAME\", \"callback_url\": \"$CALLBACK_URL\", \"id\": \"$MODEL_ID\"}")

echo "🌐 API HTTP status: $HTTP_CODE"
if [[ "$HTTP_CODE" != "200" && "$HTTP_CODE" != "202" ]]; then
  echo "❌ API did not accept the request (expected 200/202)."
  exit 1
fi

# 2) Wait for model to appear (host) OR inside container if CONTAINER is set
echo "⏳ Waiting up to 90s for model to download: $MODEL_NAME"
attempts=45
sleep_between=2

spinner='|/-\'
spin_i=0

for (( i=1; i<=attempts; i++ )); do
  # Check inside container if CONTAINER provided
  if [[ -n "$CONTAINER" ]]; then
    # Try common container cache locations
    for d in "/root/.cache/huggingface/hub/models--${MODEL_NAME//\//--}" \
             "/.cache/huggingface/hub/models--${MODEL_NAME//\//--}" \
             "/home/*/.cache/huggingface/hub/models--${MODEL_NAME//\//--}"
    do
      if docker exec "$CONTAINER" bash -lc "[ -d \"$d\" ]"; then
        echo -e "\n✅ Model found inside container '$CONTAINER' at: $d"
        exit 0
      fi
    done
  else
    # Check on host
    for d in "${CANDIDATE_DIRS[@]}"; do
      if [[ -d "$d" ]]; then
        echo -e "\n✅ Model found on host at: $d"
        exit 0
      fi
    done
  fi

  # spinner
  printf "\r${spinner:spin_i++%${#spinner}:1} Checking..."
  sleep "$sleep_between"
done

echo -e "\n❌ Model not found after waiting."

# Helpful hints
echo "🔎 Tips:"
echo "  - Your API might run as another user or in Docker."
echo "  - Set HF_HOME to the cache root if it’s custom (e.g., export HF_HOME=/shared/hf)."
echo "  - If running in Docker, set CONTAINER=<container_name> to search inside it."
echo "  - Try a tiny model: export MODEL_NAME=sshleifer/tiny-distilroberta-base"

exit 1

