#!/usr/bin/env bash
set -euo pipefail

# ── Config (override via env) ────────────────────────────────────────────────
TEST_CTN="${TEST_CTN:-llmedic-sanity-$$}"
BASE_CTN="${BASE_CTN:-download_service}"          # to auto-detect image if IMG not provided
IMG="${IMG:-$(docker inspect -f '{{.Config.Image}}' "$BASE_CTN" 2>/dev/null || true)}"
WORKDIR="${WORKDIR:-$(docker inspect -f '{{.Config.WorkingDir}}' "$BASE_CTN" 2>/dev/null || true)}"
[[ -z "${WORKDIR:-}" || "$WORKDIR" == "<no value>" ]] && WORKDIR="/app"

API_PORT="${API_PORT:-8001}"                      # port inside the container
HOST_PORT="${HOST_PORT:-8001}"                    # port on the host
MODEL_NAME="${MODEL_NAME:-sshleifer/tiny-distilroberta-base}"
CALLBACK_URL="${CALLBACK_URL:-http://localhost:9/fake_cb}" # black-hole callback
START_TIMEOUT="${START_TIMEOUT:-45}"              # seconds
POLL_SECONDS="${POLL_SECONDS:-90}"

# If you want cache to persist/inspect on host, set HF_VOL=/abs/path
HF_VOL="${HF_VOL:-}"                              # e.g., HF_VOL=/tmp/hf_cache

# ── Checks ──────────────────────────────────────────────────────────────────
if [[ -z "${IMG:-}" ]]; then
  echo "❌ Could not determine image. Provide IMG=<image> or ensure $BASE_CTN exists."
  exit 1
fi

# ── Cleanup ─────────────────────────────────────────────────────────────────
cleanup() { docker rm -f "$TEST_CTN" >/dev/null 2>&1 || true; }
trap cleanup EXIT

# ── Launch disposable container ─────────────────────────────────────────────
echo "🧪 Launching disposable container: $TEST_CTN (image: $IMG, workdir: $WORKDIR)"
docker rm -f "$TEST_CTN" >/dev/null 2>&1 || true

run_args=(
  -d --name "$TEST_CTN"
  -w "$WORKDIR"
  -e HF_HOME=/models
  -p "$HOST_PORT:$API_PORT"
)

# Option A: in-memory cache (fast; vanishes on cleanup)
if [[ -z "$HF_VOL" ]]; then
  run_args+=( --tmpfs /models:size=1g,mode=1777 )
else
  # Option B: bind mount cache to host (inspect afterwards)
  mkdir -p "$HF_VOL"
  run_args+=( -v "$HF_VOL":/models )
fi

docker run "${run_args[@]}" "$IMG" \
  sh -lc "uvicorn download_model:app --host 0.0.0.0 --port $API_PORT --ws none"

# ── Wait for API readiness ──────────────────────────────────────────────────
echo "⏳ Waiting for API on http://localhost:$HOST_PORT/ ..."
ready=false
for _ in $(seq "$START_TIMEOUT"); do
  code="$(curl -s -m 1 -o /dev/null -w '%{http_code}' "http://localhost:$HOST_PORT/")" || true
  if [[ "$code" == "200" ]]; then ready=true; break; fi
  # bail early if container died
  running="$(docker inspect -f '{{.State.Running}}' "$TEST_CTN" 2>/dev/null || echo false)"
  [[ "$running" != "true" ]] && { echo "❌ container exited early"; docker logs "$TEST_CTN" | tail -n 200; exit 1; }
  sleep 1
done
$ready || { echo "❌ API not ready within $START_TIMEOUT s"; docker logs "$TEST_CTN" | tail -n 200; exit 1; }
echo "✅ API is up."

# ── Trigger install ─────────────────────────────────────────────────────────
MODEL_ID="sanity-$(date +%s)"
echo "📡 POST /models/install  model=$MODEL_NAME  id=$MODEL_ID"
post_code="$(curl -sS -o /dev/stdout -w $'\nHTTP %{http_code}\n' \
  -X POST "http://localhost:$HOST_PORT/models/install" \
  -H 'Content-Type: application/json' \
  -d "{\"model_path\":\"$MODEL_NAME\",\"callback_url\":\"$CALLBACK_URL\",\"id\":\"$MODEL_ID\"}" \
  | awk '/^HTTP [0-9]{3}/{print $2}' | tail -n1)"
if [[ "$post_code" != "200" && "$post_code" != "202" ]]; then
  echo "❌ API did not accept request (got $post_code)"
  docker logs "$TEST_CTN" | tail -n 200 || true
  exit 1
fi
echo "✅ Request accepted: $post_code"

# ── Discover HF cache path inside the container ─────────────────────────────
echo "🔎 Resolving HF cache path inside container…"
HF_CACHE="$(docker exec "$TEST_CTN" sh -lc '
python3 - <<PY 2>/dev/null || true
try:
    from huggingface_hub.constants import HF_HUB_CACHE
    print(HF_HUB_CACHE)
except Exception:
    pass
PY
')"

if [[ -z "$HF_CACHE" ]]; then
  # fallbacks
  for cand in "/models" "/root/.cache/huggingface" "/.cache/huggingface" "/home/*/.cache/huggingface"; do
    if docker exec "$TEST_CTN" sh -lc "[ -d \"$cand\" ]" >/dev/null 2>&1; then HF_CACHE="$cand"; break; fi
  done
fi
[[ -z "$HF_CACHE" ]] && { echo "❌ Could not determine HF cache path"; exit 1; }

# normalize to /hub
if [[ "${HF_CACHE##*/}" != "hub" ]]; then HF_CACHE="$HF_CACHE/hub"; fi
MODEL_DIR_SUFFIX="models--${MODEL_NAME//\//--}"
CHECK_PATH="$HF_CACHE/$MODEL_DIR_SUFFIX"
echo "📁 Expecting snapshot at: $CHECK_PATH"

# ── Poll for snapshot directory ─────────────────────────────────────────────
echo "⏳ Polling for up to ${POLL_SECONDS}s for snapshot to appear…"
deadline=$(( $(date +%s) + POLL_SECONDS ))
spinner='|/-\' ; i=0
while (( $(date +%s) < deadline )); do
  if docker exec "$TEST_CTN" sh -lc "[ -d \"$CHECK_PATH\" ]"; then
    # optional: ensure at least one file exists
    if docker exec "$TEST_CTN" sh -lc "find \"$CHECK_PATH\" -type f | head -n1 >/dev/null"; then
      echo -e "\n✅ Model snapshot present: $CHECK_PATH"
      exit 0
    fi
  fi
  printf "\r%s waiting..." "${spinner:i++%${#spinner}:1}"
  sleep 2
done

echo -e "\n❌ Model snapshot not found within ${POLL_SECONDS}s."
echo "----- recent logs -----"
docker logs "$TEST_CTN" | tail -n 200 || true
exit 1

