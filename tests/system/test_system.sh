#!/usr/bin/env bash
set -euo pipefail

# ── Config (override via env) ────────────────────────────────────────────────
TEST_CTN="${TEST_CTN:-llmedic-dltest}"
BASE_CTN="${BASE_CTN:-download_service}"          # used to auto-detect image if IMG not set
IMG="${IMG:-$(docker inspect -f '{{.Config.Image}}' "$BASE_CTN" 2>/dev/null || true)}"
API_PORT="${API_PORT:-8001}"
MODEL_NAME="${MODEL_NAME:-sshleifer/tiny-distilroberta-base}"
TMPFS_SIZE="${TMPFS_SIZE:-200m}"                   # tmpfs size for /models in the throwaway container
START_TIMEOUT="${START_TIMEOUT:-45}"
ERROR_TIMEOUT="${ERROR_TIMEOUT:-90}"               # how long to poll logs for an error

# ── Checks ──────────────────────────────────────────────────────────────────
if [[ -z "${IMG:-}" ]]; then
  echo "❌ Could not determine image. Set IMG=<image> or ensure container $BASE_CTN exists."
  exit 1
fi

# Try to detect working dir from the base container (fallback /app)
WORKDIR="${WORKDIR:-$(docker inspect -f '{{.Config.WorkingDir}}' "$BASE_CTN" 2>/dev/null || true)}"
[[ -z "$WORKDIR" || "$WORKDIR" == "<no value>" ]] && WORKDIR="/app"

cleanup() { docker rm -f "$TEST_CTN" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "🧪 Launching throwaway test container from image: $IMG (workdir: $WORKDIR)"
docker rm -f "$TEST_CTN" >/dev/null 2>&1 || true
docker run -d --name "$TEST_CTN" \
  --privileged \
  --tmpfs /models:size=$TMPFS_SIZE,mode=1777 \
  -e HF_HOME=/models \
  -e PYTHONWARNINGS=error::UserWarning \
  -w "$WORKDIR" \
  "$IMG" sh -lc "uvicorn download_model:app --host 0.0.0.0 --port $API_PORT --ws none"

# ── Wait for API ready ──────────────────────────────────────────────────────
echo "⏳ Waiting for API to be ready on :$API_PORT ..."
for _ in $(seq "$START_TIMEOUT"); do
  RUNNING=$(docker inspect -f '{{.State.Running}}' "$TEST_CTN" 2>/dev/null || echo "false")
  if [[ "$RUNNING" != "true" ]]; then
    echo "❌ Test container exited early. Recent logs:"
    docker logs "$TEST_CTN" 2>&1 | tail -n 200 || true
    exit 1
  fi
  if docker exec "$TEST_CTN" sh -lc \
      "curl -s -m 1 -o /dev/null -w '%{http_code}' http://localhost:$API_PORT/ >/dev/null 2>&1"; then
    echo "✅ API is up."
    break
  fi
  sleep 1
done

post_install() {
  docker exec "$TEST_CTN" sh -lc \
    "curl -sS -o /dev/null -w '%{http_code}' \
      -X POST http://localhost:$API_PORT/models/install \
      -H 'Content-Type: application/json' \
      -d '{\"model_path\":\"$MODEL_NAME\",\"callback_url\":\"http://localhost:9/cb\",\"id\":\"sysfail-'$(date +%s)'\"}'"
}

logs_since() {
  local seconds=${1:-10}
  docker logs --since ${seconds}s "$TEST_CTN" 2>&1 || true
}

# Poll logs for up to ERROR_TIMEOUT seconds for any of the error markers
wait_for_error() {
  local timeout="$1"; shift
  local pattern="$*"
  local start_ts
  start_ts=$(date +%s)
  while true; do
    local now; now=$(date +%s)
    local elapsed=$((now - start_ts))
    local remain=$((timeout - elapsed))
    [[ $remain -le 0 ]] && return 1

    local L
    L="$(logs_since $((elapsed + 2)))"   # widen window as we go
    if echo "$L" | grep -Eiq "$pattern"; then
      echo "   → matched: /$pattern/"
      return 0
    fi
    sleep 2
  done
}

echo
echo "────────────────────────────────────────────────────────────────────────────"
echo "TEST 1: Disk full (ENOSPC) on /models — deterministic fill"
echo "────────────────────────────────────────────────────────────────────────────"

AVAIL_BYTES=$(docker exec "$TEST_CTN" sh -lc "df -B1 /models | awk 'NR==2{print \$4}'")
echo "Free on /models: ${AVAIL_BYTES} bytes"
LEAVE_BYTES=1                                   # leave 1 byte to force immediate failure
FILL_BYTES=$((AVAIL_BYTES - LEAVE_BYTES))
(( FILL_BYTES < 0 )) && FILL_BYTES=0
echo "Filling ${FILL_BYTES} bytes (leaving ${LEAVE_BYTES} byte free)..."

docker exec "$TEST_CTN" sh -lc '
bytes='"$FILL_BYTES"';
rm -f /models/_fill.bin;
if [ $bytes -gt 0 ]; then
  bs=1048576; count=$((bytes/bs)); rem=$((bytes%bs));
  [ $count -gt 0 ] && dd if=/dev/zero of=/models/_fill.bin bs=$bs count=$count oflag=direct 2>/dev/null || true;
  [ $rem -gt 0 ]   && dd if=/dev/zero of=/models/_fill.bin bs=$rem count=1 oflag=append conv=notrunc 2>/dev/null || true;
fi; sync'

NEW_AVAIL=$(docker exec "$TEST_CTN" sh -lc "df -B1 /models | awk 'NR==2{print \$4}'")
echo "Free now: ${NEW_AVAIL} bytes"

HTTP="$(post_install || true)"
echo "HTTP: $HTTP (endpoint returns 200 for 'started'; failure/warning shows in logs)"

# Catch HF warning or OS ENOSPC; include exact HF text
PATTERN="Error during install|No space left on device|ENOSPC|Not enough free disk space to download the file"
if wait_for_error "$ERROR_TIMEOUT" "$PATTERN"; then
  echo "✅ Disk-full scenario handled (error/warning logged)"
else
  echo "❌ Expected disk-full error/warning not observed within ${ERROR_TIMEOUT}s"
  echo "----- recent logs -----"
  docker logs "$TEST_CTN" 2>&1 | tail -n 200 || true
  exit 1
fi

docker exec "$TEST_CTN" sh -lc "rm -f /models/_fill.bin || true"

echo
echo "────────────────────────────────────────────────────────────────────────────"
echo "TEST 2: Read-only filesystem (EROFS) on /models"
echo "────────────────────────────────────────────────────────────────────────────"

docker exec "$TEST_CTN" sh -lc "mount -o remount,ro /models || true"
if docker exec "$TEST_CTN" sh -lc "touch /models/_should_fail 2>/dev/null"; then
  echo "⚠️ Remount ro failed; /models is still writable. Skipping EROFS assertion."
else
  echo "   /models is read-only as expected."
fi

HTTP="$(post_install || true)"
echo "HTTP: $HTTP (endpoint returns 200 for 'started'; failure shows in logs)"
if wait_for_error "$ERROR_TIMEOUT" "Error during install|Read-only file system|EROFS"; then
  echo "✅ Read-only scenario handled (error logged)"
else
  echo "❌ Expected read-only error not observed within ${ERROR_TIMEOUT}s"
  echo "----- recent logs -----"
  docker logs "$TEST_CTN" 2>&1 | tail -n 200 || true
  exit 1
fi

docker exec "$TEST_CTN" sh -lc "mount -o remount,rw /models || true"

echo
echo "🎉 System-level failure tests (containerized) PASSED"

