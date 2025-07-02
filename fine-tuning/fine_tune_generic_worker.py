#!/usr/bin/env python3
import os
import sys
import json
import pika
import shutil
import tempfile
import requests
import logging
from transformers import AutoTokenizer
from llamafactory.hparams import get_train_args
from llamafactory.train.tuner import run_exp

RABBIT_URL = os.environ.get("RABBIT_URL", "amqp://guest:guest@128.16.12.219:5672/")
QUEUE_NAME = os.environ.get("QUEUE_NAME", "fine_tune_requests")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
root_logger = logging.getLogger()


def process_message(ch, method, props, body):
    msg = json.loads(body)
    req_id       = msg.get("fine_tune_request_id")
    model_path   = msg.get("ai_model_path")
    raw_params   = msg.get("parameters", "{}")
    examples     = msg.get("fine_tune_data", [])
    callback_url = msg.get("callback_url")

    work_dir = tempfile.mkdtemp(prefix=f"ft_{req_id}_")
    log_file = os.path.join(work_dir, "fine_tune.log")
    task_logger = logging.getLogger(f"finetune_{req_id}")
    task_logger.setLevel(logging.INFO)
    fh = logging.FileHandler(log_file)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    task_logger.addHandler(fh)

    task_logger.info(f"Received fine-tune request {req_id}")

    status = "success"
    error  = None

    try:
        task_logger.info(f"Loading tokenizer for base model: {model_path}")
        AutoTokenizer.from_pretrained(model_path)
        task_logger.info("Base model loaded successfully.")
    except Exception as e:
        status = "fail"
        error  = f"Model load failed: {e}"
        task_logger.error(error)
        _send_callback(callback_url, req_id, status, error, task_logger)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    try:
        params = json.loads(raw_params) if isinstance(raw_params, str) else raw_params
        task_logger.info(f"Parsed fine-tuning parameters: {params}")
    except Exception as e:
        params = {}
        task_logger.warning(f"Failed to parse parameters JSON, using defaults: {e}")

    data_dir = os.path.join(work_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    ds_name  = f"request_{req_id}"
    data_file = os.path.join(data_dir, f"{ds_name}.json")
    with open(data_file, "w") as f:
        json.dump(examples, f, indent=2)
    task_logger.info(f"Wrote {len(examples)} examples to {data_file}")

    info = {
        ds_name: {
            "file_name": f"{ds_name}.json",
            "columns": {"prompt": "instruction", "query": None, "response": "output"}
        }
    }
    with open(os.path.join(data_dir, "dataset_info.json"), "w") as f:
        json.dump(info, f, indent=2)
    task_logger.info("Created dataset_info.json")

    cfg = {
        "model_name_or_path": model_path,
        "stage": "sft",
        "finetuning_type": "lora",
        "lora_target": "all",
        "lora_rank": 8,
        "lora_alpha": 16,
        "lora_dropout": 0.1,
        "dataset": ds_name,
        "dataset_dir": data_dir,
        "template": "llama3",
        "cutoff_len": 1024,
        "do_train": True,
        "do_eval": False,
        "per_device_train_batch_size": 1,
        "gradient_accumulation_steps": 1,
        "learning_rate": 2e-5,
        "num_train_epochs": 1,
        "max_steps": 1,
        "save_strategy": "steps",
        "save_steps": 1,
        "save_total_limit": 1,
        "save_only_model": False,
        "output_dir": os.path.join(work_dir, "out"),
        "overwrite_output_dir": True,
        "fp16": True,
        "gradient_checkpointing": True,
        "ddp_backend": "gloo",
        "report_to": [],
    }
    cfg.update(params)
    task_logger.info(f"Final training config: {cfg}")

    sys.argv = [sys.argv[0]]
    for k, v in cfg.items():
        sys.argv += [f"--{k.replace('_','-')}", str(v)]

    try:
        task_logger.info("Starting fine-tuning run_exp()")
        model_args, data_args, training_args, finetuning_args, generating_args = get_train_args()
        run_exp(model_args, data_args, training_args, finetuning_args, generating_args)
        task_logger.info("Fine-tuning completed successfully.")
    except Exception as e:
        status = "fail"
        error  = str(e)
        task_logger.exception("Fine-tuning failed:")
    finally:
        _send_callback(callback_url, req_id, status, error, task_logger)
        shutil.rmtree(work_dir)
        ch.basic_ack(delivery_tag=method.delivery_tag)


def _send_callback(url, req_id, status, error, logger):
    payload = {"id": req_id, "status": status}
    if error:
        payload["error"] = error
    try:
        resp = requests.post(url, json=payload, timeout=5)
        logger.info(f"Callback sent: {payload}, response: {resp.status_code}")
    except Exception as e:
        logger.error(f"Failed to send callback: {e}")


if __name__ == "__main__":
    conn = pika.BlockingConnection(pika.URLParameters(RABBIT_URL))
    chan = conn.channel()
    chan.queue_declare(queue=QUEUE_NAME, durable=True)
    chan.basic_consume(queue=QUEUE_NAME, on_message_callback=process_message)
    root_logger.info("Waiting for fine-tune requests…")
    chan.start_consuming()
