#!/usr/bin/env bash
set -euo pipefail

# ── Config (override via env) ────────────────────────────────────────────────
TEST_CTN="${TEST_CTN:-llmedic-dltest}"
BASE_CTN="${BASE_CTN:-download_service}"   # used to auto-detect image if IMG not set
IMG="${IMG:-$(docker inspect -f '{{.Config.Image}}' "$BASE_CTN" 2>/dev/null || true)}"
API_PORT="${API_PORT:-8001}"
MODEL_NAME="${MODEL_NAME:-sshleifer/tiny-distilroberta-base}"
# tiny /models; we'll fill it to simulate ENOSPC
TMPFS_SIZE="${TMPFS_SIZE:-200m}"
START_TIMEOUT="${START_TIMEOUT:-30}"

# ── Checks ──────────────────────────────────────────────────────────────────
if [[ -z "${IMG:-}" ]]; then
  echo "❌ Could not determine image. Set IMG=<image> or ensure container $BASE_CTN exists."
  exit 1
fi

# ── Cleanup on exit ─────────────────────────────────────────────────────────
cleanup() {
  docker rm -f "$TEST_CTN" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "🧪 Launching throwaway test container from image: $IMG"
docker rm -f "$TEST_CTN" >/dev/null 2>&1 || true
docker run -d --rm --name "$TEST_CTN" \
  --privileged \
  --tmpfs /models:size=$TMPFS_SIZE,mode=1777 \
  -e HF_HOME=/models \
  "$IMG" sh -lc "uvicorn download_model:app --host 0.0.0.0 --port $API_PORT"

# ── Wait for API ready ──────────────────────────────────────────────────────
echo "⏳ Waiting for API to be ready on :$API_PORT ..."
ready=0
for i in $(seq $START_TIMEOUT); do
  if docker exec "$TEST_CTN" sh -lc "curl -sS -m 1 -o /dev/null -w '%{http_code}' http://localhost:$API_PORT/ >/dev/null 2>&1"; then
    ready=1; break
  fi
  sleep 1
done
if [[ $ready -ne 1 ]]; then
  echo "❌ API not ready after ${START_TIMEOUT}s"; docker logs "$TEST_CTN" | tail -n 200; exit 1
fi
echo "✅ API is up."

post_install() {
  docker exec "$TEST_CTN" sh -lc \
    "curl -sS -o /dev/null -w '%{http_code}' \
      -X POST http://localhost:$API_PORT/models/install \
      -H 'Content-Type: application/json' \
      -d '{\"model_path\":\"$MODEL_NAME\",\"callback_url\":\"http://localhost:9/cb\",\"id\":\"sysfail-$(date +%s)\"}'"
}

logs_since() {
  local seconds=${1:-10}
  docker logs --since ${seconds}s "$TEST_CTN" 2>&1 || true
}

assert_logs_match() {
  local seconds="$1"; shift
  local pattern="$*"
  local L; L="$(logs_since "$seconds")"
  if echo "$L" | grep -Eiq "$pattern"; then
    echo "   → matched: /$pattern/"
    return 0
  else
    echo "   → did NOT match: /$pattern/"
    echo "----- recent logs -----"; echo "$L" | tail -n 120; echo "-----------------------"
    return 1
  fi
}

echo
echo "────────────────────────────────────────────────────────────────────────────"
echo "TEST 1: Disk full (ENOSPC) on /models"
echo "────────────────────────────────────────────────────────────────────────────"
# Fill tmpfs quickly; ignore failure once full
docker exec "$TEST_CTN" sh -lc "dd if=/dev/zero of=/models/_fill.bin bs=20M count=8 oflag=direct || true"

HTTP="$(post_install || true)"
echo "HTTP: $HTTP (endpoint returns 200 for 'started'; failure is in logs)"
sleep 3
# Expect worker to log an install error (disk full / ENOSPC)
assert_logs_match 15 "Error during install|No space left on device|ENOSPC" \
  && echo "✅ Disk-full scenario handled (error logged)" \
  || { echo "❌ Expected disk-full error not observed"; exit 1; }

# Free space for next test
docker exec "$TEST_CTN" sh -lc "rm -f /models/_fill.bin || true"

echo
echo "────────────────────────────────────────────────────────────────────────────"
echo "TEST 2: Read-only filesystem (EROFS) on /models"
echo "────────────────────────────────────────────────────────────────────────────"
# Remount /models read-only (requires --privileged; we set that)
docker exec "$TEST_CTN" sh -lc "mount -o remount,ro /models"
# Quick write sanity (should fail)
if docker exec "$TEST_CTN" sh -lc "touch /models/_should_fail 2>/dev/null"; then
  echo "⚠️ Remount ro failed; /models is still writable. Skipping EROFS assertion."
else
  echo "   /models is read-only as expected."
fi

HTTP="$(post_install || true)"
echo "HTTP: $HTTP (endpoint returns 200 for 'started'; failure is in logs)"
sleep 3
# Expect worker to log read-only / write failure
assert_logs_match 15 "Error during install|Read-only file system|EROFS" \
  && echo "✅ Read-only scenario handled (error logged)" \
  || { echo "❌ Expected read-only error not observed"; exit 1; }

# Restore rw for clean exit
docker exec "$TEST_CTN" sh -lc "mount -o remount,rw /models || true"

echo
echo "🎉 System-level failure tests (containerized) PASSED"

