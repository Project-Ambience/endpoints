#!/usr/bin/env bash
set -euo pipefail

# ── Config (override via env) ────────────────────────────────────────────────
TEST_CTN="${TEST_CTN:-llmedic-fttest}"
BASE_CTN="${BASE_CTN:-finetuning_service}"  # used to auto-detect image if IMG not set
IMG="${IMG:-$(docker inspect -f '{{.Config.Image}}' "$BASE_CTN" 2>/dev/null || true)}"

# Internal API ports to try *inside* the container (no host -p mapping)
PORT_CANDIDATES=(${API_PORT:-} 8001 8002 8000)

# Base model kept tiny so CPU training finishes quickly
BASE_MODEL="${BASE_MODEL:-prajjwal1/bert-tiny}"

# Candidate POST routes to try (first that returns 200/202 wins).
# You can force one via FINETUNE_PATH=/your/route
ROUTE_CANDIDATES=(
  "${FINETUNE_PATH:-}"
  "/finetune/start" "/finetune" "/train"
  "/api/finetune/start" "/api/finetune" "/api/train"
  "/v1/finetune/start" "/v1/finetune" "/v1/train"
)

START_TIMEOUT="${START_TIMEOUT:-90}"      # seconds to wait for API readiness
ARTIFACT_TIMEOUT="${ARTIFACT_TIMEOUT:-240}" # seconds to wait for artifacts

# ── Pre-flight checks ────────────────────────────────────────────────────────
if [[ -z "${IMG:-}" ]]; then
  echo "❌ Could not determine image. Set IMG=<image> or ensure container $BASE_CTN exists."
  exit 1
fi

# Make tiny dataset on host and mount read-only
DATA_DIR="$(mktemp -d)"
trap 'rm -rf "$DATA_DIR" || true' EXIT

mkdir -p "$DATA_DIR"
cat > "${DATA_DIR}/train.csv" <<'CSV'
text,label
This movie was great!,1
I really enjoyed the acting.,1
Terrible plot and boring.,0
Absolutely fantastic!,1
Would not recommend.,0
CSV
cat > "${DATA_DIR}/eval.csv" <<'CSV'
text,label
Great film!,1
Bad film.,0
CSV

# Unique job/output directory inside the container
JOB_ID="ft-$(date +%s)"
OUT_DIR_IN_CTN="/models/finetunes/${JOB_ID}"

cleanup_ctn() { docker rm -f "$TEST_CTN" >/dev/null 2>&1 || true; }
trap cleanup_ctn EXIT

echo "🧪 Launching throwaway fine-tune container from image: $IMG"
docker rm -f "$TEST_CTN" >/dev/null 2>&1 || true
docker run -d --name "$TEST_CTN" \
  -e HF_HOME=/models \
  -v "${DATA_DIR}":/data:ro \
  "$IMG" sh -lc "./start_finetune.sh"

# ── Discover working API port inside the container ──────────────────────────
discover_port() {
  for p in "${PORT_CANDIDATES[@]}"; do
    [[ -z "$p" ]] && continue
    # Prefer FastAPI markers; fall back to any 200 on '/'
    if docker exec "$TEST_CTN" sh -lc \
         "curl -s -m 1 -o /dev/null -w '%{http_code}' http://localhost:$p/openapi.json || true" \
         | grep -q '^200$'; then
      echo "$p"; return 0
    fi
    if docker exec "$TEST_CTN" sh -lc \
         "curl -s -m 1 -o /dev/null -w '%{http_code}' http://localhost:$p/docs || true" \
         | grep -q '^200$'; then
      echo "$p"; return 0
    fi
    # last resort: root path
    if docker exec "$TEST_CTN" sh -lc \
         "curl -s -m 1 -o /dev/null -w '%{http_code}' http://localhost:$p/ || true" \
         | grep -Eq '^(200|204)$'; then
      echo "$p"; return 0
    fi
  done
  return 1
}

echo "⏳ Waiting for API readiness inside container..."
API_PORT_FOUND=""
deadline=$(( $(date +%s) + START_TIMEOUT ))
while [[ -z "$API_PORT_FOUND" && $(date +%s) -lt $deadline ]]; do
  if API_PORT_FOUND="$(discover_port)"; then
    echo "✅ API appears up on internal port: $API_PORT_FOUND"
    break
  fi
  sleep 2
done
if [[ -z "$API_PORT_FOUND" ]]; then
  echo "❌ API did not become ready within ${START_TIMEOUT}s. Recent logs:"
  docker logs "$TEST_CTN" | tail -n 200 || true
  exit 1
fi

# ── Pick a working route ─────────────────────────────────────────────────────
valid_routes=()
for r in "${ROUTE_CANDIDATES[@]}"; do
  [[ -z "$r" ]] && continue
  valid_routes+=("$r")
done
if [[ ${#valid_routes[@]} -eq 0 ]]; then
  valid_routes=("/finetune/start" "/finetune" "/train")
fi

pick_route() {
  for r in "${valid_routes[@]}"; do
    # Probe with OPTIONS (cheap) then POST with a dry-run-ish body (max_steps small)
    code="$(docker exec "$TEST_CTN" sh -lc \
      "curl -s -m 1 -o /dev/null -w '%{http_code}' -X OPTIONS http://localhost:$API_PORT_FOUND$r || true")"
    if [[ "$code" =~ ^(200|204|405)$ ]]; then
      # try a lightweight POST just to see if endpoint exists (ignore body validation for now)
      code2="$(docker exec "$TEST_CTN" sh -lc \
        "curl -s -m 2 -o /dev/null -w '%{http_code}' -X POST http://localhost:$API_PORT_FOUND$r -H 'Content-Type: application/json' -d '{}' || true")"
      if [[ "$code2" =~ ^(200|202|400|422)$ ]]; then
        echo "$r"; return 0
      fi
    fi
  done
  return 1
}

ROUTE_FOUND=""
if ! ROUTE_FOUND="$(pick_route)"; then
  echo "❌ Could not discover a finetune route. Try setting FINETUNE_PATH=/your/route"
  echo "Routes tried: ${valid_routes[*]}"
  echo "Recent logs:"
  docker logs "$TEST_CTN" | tail -n 200 || true
  exit 1
fi
echo "🔎 Using route: $ROUTE_FOUND"

# ── Kick off a tiny fine-tune job ───────────────────────────────────────────
echo "📡 POST $ROUTE_FOUND  model=$BASE_MODEL  job_id=$JOB_ID"
POST_OUT="$(docker exec "$TEST_CTN" sh -lc "
  curl -sS -o /dev/stdout -w '\nHTTP %{http_code}\n' \
    -X POST http://localhost:$API_PORT_FOUND$ROUTE_FOUND \
    -H 'Content-Type: application/json' \
    -d '{
          \"base_model\": \"${BASE_MODEL}\",
          \"train_csv\": \"/data/train.csv\",
          \"eval_csv\": \"/data/eval.csv\",
          \"output_dir\": \"${OUT_DIR_IN_CTN}\",
          \"epochs\": 1,
          \"per_device_train_batch_size\": 4,
          \"per_device_eval_batch_size\": 4,
          \"learning_rate\": 5e-5,
          \"seed\": 42,
          \"max_steps\": 20
        }'
")"
echo "$POST_OUT"
if ! echo "$POST_OUT" | grep -qE 'HTTP (200|202)'; then
  echo "❌ Fine-tune API did not accept the request."
  docker logs "$TEST_CTN" | tail -n 200 || true
  exit 1
fi

# ── Poll for training artefacts ─────────────────────────────────────────────
echo "⏳ Waiting for training artefacts in: ${OUT_DIR_IN_CTN}"
deadline=$(( $(date +%s) + ARTIFACT_TIMEOUT ))
while (( $(date +%s) < deadline )); do
  if docker exec "$TEST_CTN" sh -lc \
      "[ -f '${OUT_DIR_IN_CTN}/pytorch_model.bin' ] && [ -f '${OUT_DIR_IN_CTN}/trainer_state.json' ] && [ -f '${OUT_DIR_IN_CTN}/config.json' ]"; then
    echo "✅ Fine-tune artefacts present:"
    docker exec "$TEST_CTN" sh -lc "ls -l '${OUT_DIR_IN_CTN}' | head -n 50"
    exit 0
  fi
  # quick failure detection
  if docker logs "$TEST_CTN" 2>&1 | grep -Eiq "RuntimeError|Traceback|CUDA|HPU|error during training"; then
    echo "❌ Training failure observed in logs:"
    docker logs "$TEST_CTN" | tail -n 200 || true
    exit 1
  fi
  sleep 3
done

echo "❌ Timed out waiting for training artefacts after ${ARTIFACT_TIMEOUT}s."
docker logs "$TEST_CTN" | tail -n 200 || true
exit 1

