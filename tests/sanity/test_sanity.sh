#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Running model download test..."

# ── Config (override via env)
API_URL="${API_URL:-http://localhost:8000/models/install}"
MODEL_NAME="${MODEL_NAME:-sshleifer/tiny-distilroberta-base}"
MODEL_ID="test-download-$(date +%s)"
CALLBACK_URL="${CALLBACK_URL:-http://host.docker.internal:9999/fake_callback}"
CONTAINER="${CONTAINER:-}"  

_model_suffix() {
  printf "models--%s\n" "${MODEL_NAME//\//--}"
}

_hf_cache_in_container() {
  # Ask Python first; fall back to env/defaults
  docker exec "$CONTAINER" bash -lc '
python3 - <<PY 2>/dev/null || true
try:
    from huggingface_hub.constants import HF_HUB_CACHE
    print(HF_HUB_CACHE)
except Exception:
    pass
PY
' | tr -d "\r"
}

_hf_cache_on_host() {
python3 - <<PY 2>/dev/null || true
try:
    from huggingface_hub.constants import HF_HUB_CACHE
    print(HF_HUB_CACHE)
except Exception:
    pass
PY
}

_trim_trailing_slash() {
  local p="${1:-}"
  printf "%s" "${p%/}"
}

_post_from_container() {
  docker exec "$CONTAINER" bash -lc \
    "curl -sS -o /dev/stdout -w '\nHTTP %{http_code}\n' \
      -X POST http://localhost:${API_PORT:-$(echo "$API_URL" | awk -F: '{print $3}' | awk -F/ "{print \$1}")}$(echo "$API_URL" | sed -E 's|https?://[^/]+||') \
      -H 'Content-Type: application/json' \
      -d '{\"model_path\":\"$MODEL_NAME\",\"callback_url\":\"$CALLBACK_URL\",\"id\":\"$MODEL_ID\"}'"
}

_post_from_host() {
  curl -sS -o /dev/stdout -w "\nHTTP %{http_code}\n" \
    -X POST "$API_URL" \
    -H "Content-Type: application/json" \
    -d "{\"model_path\":\"$MODEL_NAME\",\"callback_url\":\"$CALLBACK_URL\",\"id\":\"$MODEL_ID\"}"
}

# ── 1) Trigger install via API
if [[ -n "$CONTAINER" ]]; then
  echo "📡 Sending install request from inside container: $CONTAINER"
  POST_OUT="$(_post_from_container || true)"
else
  echo "📡 Sending install request to API: $API_URL"
  POST_OUT="$(_post_from_host || true)"
fi

HTTP_CODE="$(printf "%s" "$POST_OUT" | sed -n 's/^HTTP \([0-9][0-9][0-9]\).*/\1/p' | tail -n1)"
echo "🌐 API HTTP status: ${HTTP_CODE:-unknown}"
if [[ "${HTTP_CODE:-}" != "200" && "${HTTP_CODE:-}" != "202" ]]; then
  echo "❌ API did not accept the request (expected 200/202). Full output:"
  echo "$POST_OUT"
  exit 1
fi

# ── 2) Determine HF cache root and build model path
MODEL_DIR_SUFFIX="$(_model_suffix)"

if [[ -n "$CONTAINER" ]]; then
  echo "🔎 Detecting Hugging Face cache inside container..."
  HF_CACHE="$(_hf_cache_in_container)"
  if [[ -z "$HF_CACHE" ]]; then
    # fallbacks
    for cand in "/models" "/root/.cache/huggingface" "/.cache/huggingface" "/home/*/.cache/huggingface"; do
      if docker exec "$CONTAINER" bash -lc "[ -d '$cand' ]" >/dev/null 2>&1; then
        HF_CACHE="$cand"
        break
      fi
    done
  fi
  if [[ -z "$HF_CACHE" ]]; then
    echo "❌ Could not determine HF cache inside container."
    exit 1
  fi
  HF_CACHE="$(_trim_trailing_slash "$HF_CACHE")"
  # If HF_CACHE is a parent (like /models), the hub folder is usually HF_CACHE/hub
  # If HF_CACHE already ends with '/hub', use it directly.
  if [[ "${HF_CACHE##*/}" != "hub" ]]; then
    HF_CACHE="$HF_CACHE/hub"
  fi
  CHECK_PATH="$HF_CACHE/$MODEL_DIR_SUFFIX"
  echo "📁 Will check inside container at: $CHECK_PATH"
else
  echo "🔎 Detecting Hugging Face cache on host..."
  HF_CACHE="$(_hf_cache_on_host)"
  if [[ -z "$HF_CACHE" ]]; then
    HF_CACHE="${HF_HOME:-$HOME/.cache/huggingface}"
  fi
  HF_CACHE="$(_trim_trailing_slash "$HF_CACHE")"
  if [[ "${HF_CACHE##*/}" != "hub" ]]; then
    HF_CACHE="$HF_CACHE/hub"
  fi
  CHECK_PATH="$HF_CACHE/$MODEL_DIR_SUFFIX"
  echo "📁 Will check on host at: $CHECK_PATH"
fi

# ── 3) Poll for completion (up to 90s)
echo "⏳ Waiting up to 90s for model to download: $MODEL_NAME"
attempts=45
sleep_between=2
spinner='|/-\'
spin_i=0

for (( i=1; i<=attempts; i++ )); do
  if [[ -n "$CONTAINER" ]]; then
    if docker exec "$CONTAINER" bash -lc "[ -d '$CHECK_PATH' ]" >/dev/null 2>&1; then
      echo -e "\n✅ Model found inside container at: $CHECK_PATH"
      exit 0
    fi
  else
    if [[ -d "$CHECK_PATH" ]]; then
      echo -e "\n✅ Model found on host at: $CHECK_PATH"
      exit 0
    fi
  fi
  printf "\r${spinner:spin_i++%${#spinner}:1} Checking..."
  sleep "$sleep_between"
done

echo -e "\n❌ Model not found after waiting."
echo "🪪 Debug tips:"
echo "  • Check container logs: docker logs ${CONTAINER:-<your-container>}"
echo "  • Ensure API port is correct (try API_URL=http://localhost:8001/models/install)"
echo "  • Verify HF_HOME/HF_HUB_CACHE and mounts (e.g., -v /shared/models:/models)"
exit 1

