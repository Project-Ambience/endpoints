#!/usr/bin/env bash
# test_finetune.sh — publish → consume → launch → archive sanity for the fine-tuning worker

set -euo pipefail

# -------- Config (override via env before running) --------
WORKER_CONT="${WORKER_CONT:-finetuning_service}"
RABBIT_CONT="${RABBIT_CONT:-web-demo-rabbitmq-1}"
QUEUE_NAME="${QUEUE_NAME:-model_fine_tune_requests}"
MODEL_ID="${MODEL_ID:-sshleifer/tiny-gpt2}"
# Same format/vhost the worker logs show (note %2F for '/')
RABBIT_URL="${RABBIT_URL:-amqp://guest:guest@128.16.12.219:5672/%2F?heartbeat=0}"

# Use a simple numeric RUN_ID that won't trip shells
if [ $# -ge 1 ]; then
  RUN_ID="$1"
else
  # seconds + pid for uniqueness without arithmetic tricks
  RUN_ID="$(date +%s)$$"
fi

# -------- Tiny helpers (no fancy bash features) --------
say() { printf "%s\n" "$*"; }
cyan()  { printf "\033[36m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
yellow(){ printf "\033[33m%s\033[0m\n" "$*"; }
red()   { printf "\033[31m%s\033[0m\n" "$*"; }

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    red "Missing required command: $1"
    exit 1
  fi
}

# -------- Main --------
need docker

cyan "📦 Ensuring base model cached inside ${WORKER_CONT}: ${MODEL_ID}"
docker exec "${WORKER_CONT}" sh -lc "python - <<'PY'
from transformers import AutoModelForCausalLM, AutoTokenizer
m = '''${MODEL_ID}'''
AutoTokenizer.from_pretrained(m)
AutoModelForCausalLM.from_pretrained(m)
print('✅ cached', m)
PY"

cyan "⏳ Checking worker AMQP reachability"
docker exec "${WORKER_CONT}" sh -lc "python - <<'PY'
import pika
url='''${RABBIT_URL}'''
p=pika.BlockingConnection(pika.URLParameters(url))
p.close()
print('✅ Worker can reach RabbitMQ at', url)
PY"

cyan "📡 Publishing fine-tune job  id=${RUN_ID}  model=${MODEL_ID}  queue=${QUEUE_NAME}"
docker exec "${WORKER_CONT}" sh -lc "python - <<'PY'
import json, pika
url='''${RABBIT_URL}'''
queue='''${QUEUE_NAME}'''
msg={
  'fine_tune_request_id': '''${RUN_ID}''',
  'ai_model_path': '''${MODEL_ID}''',
  'callback_url': 'http://127.0.0.1:9/cb',  # 404 is fine for this test
  # IMPORTANT: correct key expected by the worker:
  'fine_tune_data': [{'input':'Hello','output':'World'}],
  # Nudge single device; worker may ignore, but harmless
  'world_size': 1,
  'num_train_epochs': 1
}
conn=pika.BlockingConnection(pika.URLParameters(url))
ch=conn.channel()
ch.queue_declare(queue=queue, durable=True)
ch.basic_publish(exchange='', routing_key=queue, body=json.dumps(msg))
conn.close()
print('✅ published to', queue)
PY"

# Give the worker a moment to pick it up
sleep 3

cyan "🔎 Verifying the worker picked up request ${RUN_ID}"
docker logs "${WORKER_CONT}" 2>&1 | grep -nE "Processing fine-tune request ${RUN_ID}" -A4 -B4 || true

cyan "🗂 Checking per-run temp working dir"
docker exec "${WORKER_CONT}" sh -lc "ls -d /tmp/ft_${RUN_ID}_* 2>/dev/null || echo 'no /tmp job dir yet'"

cyan "🧾 Training command line used (last few \"Command:\" lines)"
docker exec "${WORKER_CONT}" sh -lc "grep -n 'Command:' /tmp/logs/fine_tune_service.log | tail -n 3 || true"


cyan "📬 Queue depth and counters"
docker exec "$RABBIT_CONT" \
  rabbitmqctl list_queues name messages messages_ready messages_unacknowledged \
  | grep -E "^(name|${QUEUE_NAME})" || true

if command -v curl >/dev/null 2>&1; then
  curl -s -u guest:guest "http://localhost:15672/api/queues/%2F/${QUEUE_NAME}" \
    | jq '.messages,.message_stats.publish,.message_stats.ack' || true
fi


yellow "⏳ Waiting briefly for the run to finish/archive (failure is OK for plumbing)"
sleep 25

cyan "🗜 Archive folder (exists even on failure)"
docker exec "${WORKER_CONT}" sh -lc "ls -d /app/endpoints/fine-tuning/finetune_runs/run_${RUN_ID}* 2>/dev/null || echo 'no archive yet'"

cyan "🧩 LoRA adapter path (only on success)"
docker exec "${WORKER_CONT}" sh -lc "[ -d /models/tiny-gpt2_${RUN_ID} ] && echo 'adapter present' || echo 'no adapter (fail or still running)'"

# Outcome summary
if docker exec "${WORKER_CONT}" sh -lc "[ -d /app/endpoints/fine-tuning/finetune_runs/run_${RUN_ID}_fail ]"; then
  yellow "Result: ✅ Pipeline OK (message → consume → launch → archive). Training failed (expected on non-Gaudi hosts)."
elif docker exec "${WORKER_CONT}" sh -lc "[ -d /app/endpoints/fine-tuning/finetune_runs/run_${RUN_ID} ]"; then
  green  "Result: 🎉 Success. Pipeline OK and adapter saved."
else
  red    "Result: 🤔 No archive yet. Check worker logs."
fi

