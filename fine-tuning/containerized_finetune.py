from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import docker
import docker.errors
import pika
import requests
from transformers import AutoConfig


RABBIT_URL = os.environ.get("RABBIT_URL", "amqp://guest:guest@localhost:5672/?heartbeat=0")
START_SIGNAL_URL_TEMPLATE = os.environ.get(
    "START_SIGNAL_URL_TEMPLATE",
    "http://128.16.12.219:5091/api/model_fine_tune_requests/{request_id}/start_processing"
)
QUEUE_NAME = os.environ.get("QUEUE_NAME", "model_fine_tune_requests")
ARCHIVE_ROOT = os.environ.get("ARCHIVE_ROOT", "/app/endpoints/fine-tuning/finetune_runs")
MODELS_ROOT = os.environ.get("MODELS_ROOT", "/models")

DOCKER_IMAGE = os.environ.get("DOCKER_IMAGE", "ft-habana:latest")
DOCKERFILE_DIR = os.environ.get("DOCKERFILE_DIR", "/app/endpoints/")

DEFAULT_DEEPSPEED_CONFIG = os.environ.get(
    "DEEPSPEED_CONFIG",
    "/app/optimum-habana/examples/language-modeling/llama3_ds_zero1_config.json",
)
FINE_TUNE_TIMEOUT = int(os.environ.get("FINE_TUNE_TIMEOUT", "7200"))
CALLBACK_TIMEOUT = int(os.environ.get("CALLBACK_TIMEOUT", "10"))
LOG_DIR = os.environ.get("LOG_DIR", "/tmp/logs")


@dataclass
class FineTuneConfig:
    world_size: int = 4
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 1
    per_device_eval_batch_size: int = 1
    gradient_accumulation_steps: int = 16
    save_strategy: str = "no"
    eval_strategy: str = "epoch"
    eval_steps: int = 50
    learning_rate: float = 5e-5
    warmup_ratio: float = 0.1
    lr_scheduler_type: str = "linear"
    max_grad_norm: float = 1.0
    logging_steps: int = 10
    lora_rank: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.05
    max_seq_length: int = 2048
    adam_epsilon: float = 1e-08
    cache_size_limit: int = 64
    deepspeed_config: str = DEFAULT_DEEPSPEED_CONFIG
    lora_target_modules: List[str] = field(default_factory=list)


class FineTuneProcessor:
    def __init__(self) -> None:
        self.client = docker.from_env()
        self._ensure_image()
        self._setup_logging()
        self._ensure_directories()

    def _ensure_image(self) -> None:
        try:
            self.client.images.get(DOCKER_IMAGE)
            print(f"[start‑up] Using existing Docker image '{DOCKER_IMAGE}'.")
        except docker.errors.ImageNotFound:
            print(f"[start‑up] Image '{DOCKER_IMAGE}' not found – building from '{DOCKERFILE_DIR}'.")
            img, build_logs = self.client.images.build(path=DOCKERFILE_DIR, tag=DOCKER_IMAGE, rm=True)
            for chunk in build_logs:
                if "stream" in chunk:
                    sys.stdout.write(chunk["stream"])
            print(f"[start‑up] Built image '{DOCKER_IMAGE}'.")

    def _setup_logging(self) -> None:
        os.makedirs(LOG_DIR, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(os.path.join(LOG_DIR, "fine_tune_service.log"), mode="a"),
            ],
        )
        self.logger = logging.getLogger("FineTune‑Container")

    def _ensure_directories(self) -> None:
        for path in (ARCHIVE_ROOT, MODELS_ROOT, LOG_DIR):
            os.makedirs(path, exist_ok=True)
            self.logger.info(f"Ensured directory exists: {path}")

    @staticmethod
    def validate_message(msg: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        required = ["fine_tune_request_id", "ai_model_path", "callback_url"]
        for fld in required:
            if fld not in msg:
                return False, f"Missing required field: {fld}"
        if not isinstance(msg.get("fine_tune_data", []), list) or len(msg.get("fine_tune_data", [])) == 0:
            return False, "fine_tune_data must be a non‑empty list"
        return True, None

    @staticmethod
    def prepare_training_data(examples: List[Dict[str, Any]], data_dir: str, req_id: str) -> Tuple[str, str]:
        train_path = os.path.join(data_dir, f"train_{req_id}.json")
        val_path = os.path.join(data_dir, f"val_{req_id}.json")

        for idx, ex in enumerate(examples):
            if not isinstance(ex, dict):
                raise ValueError(f"Example {idx} is not a dict")
            if "input" not in ex and "text" not in ex:
                logging.getLogger("FineTune‑Container").warning(f"Example {idx} missing 'input' or 'text'.")

        if len(examples) > 1:
            split = max(1, int(len(examples) * 0.9))
            train_data, val_data = examples[:split], examples[split:]
        else:
            train_data, val_data = examples, examples

        os.makedirs(data_dir, exist_ok=True)
        with open(train_path, "w", encoding="utf-8") as fh:
            json.dump(train_data, fh, indent=2, ensure_ascii=False)
        with open(val_path, "w", encoding="utf-8") as fh:
            json.dump(val_data, fh, indent=2, ensure_ascii=False)

        return train_path, val_path

    @staticmethod
    def get_model_info(model_path: str) -> Tuple[str, List[str]]:
        try:
            model_name = Path(model_path).name.lower()
            safe_name = "".join(c if (c.isalnum() or c in "-_") else "_" for c in model_name)
            config = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
            model_type = getattr(config, "model_type", "unknown").lower()
            tm_map = {
                "llama": ["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
                "mistral": ["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
                "gemma": ["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
                "qwen": ["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
                "phi": ["q_proj", "v_proj", "dense", "fc1", "fc2"],
                "gpt": ["c_attn", "c_proj", "c_fc"],
                "bert": ["query", "key", "value", "dense"],
                "roberta": ["query", "key", "value", "dense"],
            }
            return safe_name, tm_map.get(model_type, ["q_proj", "v_proj", "k_proj", "o_proj"])
        except Exception as exc:
            logging.getLogger("FineTune‑Container").warning(f"get_model_info failed: {exc}")
            return "unknown_model", ["q_proj", "v_proj"]


    @staticmethod
    def build_command(cfg: FineTuneConfig, model_mount: str, train_json: str, val_json: str, out_dir: str,
                      target_modules: List[str]) -> List[str]:
        cmd = [
            "python", "/app/optimum-habana/examples/gaudi_spawn.py",
            "--world_size", str(cfg.world_size),
            "--use_deepspeed",
            "/app/optimum-habana/examples/language-modeling/run_lora_clm.py",
            "--model_name_or_path", model_mount,
            "--train_file", train_json,
            "--validation_file", val_json,
            "--do_train", "--do_eval",
            "--bf16", "True",
            "--output_dir", out_dir,
            "--num_train_epochs", str(cfg.num_train_epochs),
            "--per_device_train_batch_size", str(cfg.per_device_train_batch_size),
            "--per_device_eval_batch_size", str(cfg.per_device_eval_batch_size),
            "--gradient_accumulation_steps", str(cfg.gradient_accumulation_steps),
            "--save_strategy", cfg.save_strategy,
            "--eval_strategy", cfg.eval_strategy,
            "--eval_steps", str(cfg.eval_steps),
            "--learning_rate", str(cfg.learning_rate),
            "--warmup_ratio", str(cfg.warmup_ratio),
            "--lr_scheduler_type", cfg.lr_scheduler_type,
            "--max_grad_norm", str(cfg.max_grad_norm),
            "--logging_steps", str(cfg.logging_steps),
            "--use_habana", "--use_lazy_mode", "False",
            "--throughput_warmup_steps", "3",
            "--lora_rank", str(cfg.lora_rank),
            "--lora_alpha", str(cfg.lora_alpha),
            "--lora_dropout", str(cfg.lora_dropout),
            "--max_seq_length", str(cfg.max_seq_length),
            "--adam_epsilon", str(cfg.adam_epsilon),
            "--deepspeed", cfg.deepspeed_config,
            "--torch_compile_backend", "hpu_backend",
            "--torch_compile", "--fp8",
            "--use_flash_attention", "True", "--flash_attention_causal_mask", "True",
            "--cache_size_limit", str(cfg.cache_size_limit),
            "--use_regional_compilation", "--compile_from_sec_iteration",
            "--allow_unspec_int_on_nn_module", "True",
        ]
        if target_modules:
            cmd.append("--lora_target_modules")
            cmd.extend(target_modules)

        return cmd


    def send_callback(self, url: str, req_id: str, status: str, *, error: Optional[str] = None,
                      adapter_path: Optional[str] = None) -> None:
        payload: Dict[str, Any] = {"id": req_id, "status": status, "timestamp": time.time()}
        if error:
            payload["error"] = error
        if adapter_path:
            payload["adapter_path"] = adapter_path
        try:
            r = requests.post(url, json=payload, timeout=CALLBACK_TIMEOUT)
            r.raise_for_status()
            self.logger.info(f"Callback sent → {payload}")
        except Exception as exc:
            self.logger.error(f"Callback failed: {exc}")


    def send_start_signal(self, req_id: str):
        start_url = START_SIGNAL_URL_TEMPLATE.format(request_id=req_id)
        try:
            self.logger.info(f"Sending start-processing signal to {start_url}")
            resp = requests.post(start_url, timeout=5)
            resp.raise_for_status()
            self.logger.info(f"Start-processing signal sent successfully: {resp.status_code}")
        except Exception as e:
            self.logger.error(f"Failed to send start-processing signal: {e}")

   
    def process_message(self, ch, method, props, body: bytes):  
        req_id: Optional[str] = None
        callback_url: Optional[str] = None
        work_dir: Optional[str] = None
        task_logger: Optional[logging.Logger] = None

        def archive_run(suffix: str = "") -> None:
            if not work_dir or not req_id:
                return
            archive_dir = os.path.join(ARCHIVE_ROOT, f"run_{req_id}{suffix}")
            try:
                shutil.copytree(work_dir, archive_dir, dirs_exist_ok=True)
                if task_logger:
                    task_logger.info(f"Archived workspace → {archive_dir}")
            except Exception as exc:
                if task_logger:
                    task_logger.warning(f"Archive failed: {exc}")

        try:
            msg = json.loads(body.decode("utf-8"))
            req_id = msg.get("fine_tune_request_id")
            callback_url = msg.get("callback_url")

            ok, err = self.validate_message(msg)
            if not ok:
                self.logger.error(f"Invalid message {req_id}: {err}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return

            model_path = msg["ai_model_path"]
            examples = msg["fine_tune_data"]
            raw_params = msg.get("parameters", "{}")

            SHARED_TMP_ROOT = os.environ.get("SHARED_TMP_ROOT", "/shared/tmp")
            os.makedirs(SHARED_TMP_ROOT, exist_ok=True)
            work_dir = tempfile.mkdtemp(prefix=f"ft_{req_id}_", dir=SHARED_TMP_ROOT)
            # work_dir = tempfile.mkdtemp(prefix=f"ft_{req_id}_")
            
            log_file = os.path.join(work_dir, "fine_tune.log")
            task_logger = logging.getLogger(f"finetune_{req_id}")
            task_logger.setLevel(logging.INFO)
            handler = logging.FileHandler(log_file)
            handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
            task_logger.addHandler(handler)

            task_logger.info(f"Processing fine‑tune request {req_id}")
            task_logger.info(f"Model path: {model_path}")
            task_logger.info(f"Examples: {len(examples)} records")

            try:
                params = json.loads(raw_params) if isinstance(raw_params, str) else raw_params
            except json.JSONDecodeError as exc:
                task_logger.warning(f"Failed to parse parameters JSON, using defaults: {exc}")
                params = {}
            task_logger.info(f"User parameters: {params}")

            safe_model_name, default_target_modules = self.get_model_info(model_path)
            cfg = FineTuneConfig()
            for k, v in params.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
                    task_logger.info(f"  cfg.{k} = {v}")

            target_modules = params.get("lora_target_modules", default_target_modules)
            cfg.lora_target_modules = target_modules  
            task_logger.info(f"LoRA target modules: {target_modules}")

            data_dir = os.path.join(work_dir, "data")
            output_dir = os.path.join(work_dir, "output")
            os.makedirs(output_dir, exist_ok=True)

            train_path, val_path = self.prepare_training_data(examples, data_dir, req_id)

            cmd = self.build_command(
                cfg,
                model_path, 
                f"/workspace/data/{Path(train_path).name}",
                f"/workspace/data/{Path(val_path).name}",
                "/workspace/output",
                target_modules,
            )
            
            task_logger.info("Docker command: %s", " ".join(cmd))

            volumes = {
                work_dir: {"bind": "/workspace", "mode": "rw"},
                "/shared/models": {"bind": "/models", "mode": "ro"},
            }

            env = os.environ.copy()
            env.update({
                "DS_ACCELERATOR": "hpu",
                "DEEPSPEED_HPU": "1",
                "USE_HPU": "1",
                "PT_TE_CUSTOM_OP": "1",
                "PT_HPU_LAZY_MODE": "0",   
                "PT_HPU_ENABLE_REFINE_DYNAMIC_SHAPES": "1",
                "PT_HPU_VERBOSE": "1",
                "HCL_LOG_LEVEL": "INFO",
                "PYTHONUNBUFFERED": "1",
                "HABANA_VISIBLE_DEVICES": ",".join(str(i) for i in range(int(cfg.world_size))),
            })

            hpu_nodes = []
            for i in range(16): 
                p = f"/dev/accel{i}"
                if os.path.exists(p):
                    hpu_nodes.append(p)
            if not hpu_nodes and os.path.isdir("/dev/habanalabs"): 
                for n in os.listdir("/dev/habanalabs"):
                    full = os.path.join("/dev/habanalabs", n)
                    if os.path.exists(full):
                        hpu_nodes.append(full)
            device_maps = [f"{d}:{d}" for d in hpu_nodes]

            container = self.client.containers.run(
                DOCKER_IMAGE,
                command=cmd,
                volumes=volumes,
                working_dir="/workspace",
                detach=True,
                stdout=True,
                stderr=True,
                remove=True,
                runtime="habana",
                environment=env,         
                devices=device_maps    
            )
            task_logger.info("Container %s launched", container.short_id)
            task_logger.info(f"Starting Intel Gaudi fine-tuning in container: {container.short_id}...")
            task_logger.info(f"Command: {' '.join(cmd)}")
            self.send_start_signal(req_id)

            start_time = time.time()
            for line in container.logs(stream=True):
                decoded = line.decode().rstrip()
                task_logger.info(decoded)
                if time.time() - start_time > FINE_TUNE_TIMEOUT:
                    container.kill()
                    raise TimeoutError("Fine‑tune timed out")

            exit_res = container.wait()
            status_code = exit_res.get("StatusCode", 1)
            task_logger.info("Container exited with code %s", status_code)
            if status_code != 0:
                raise RuntimeError(f"Container exit code {status_code}")

            adapter_dest = os.path.join(MODELS_ROOT, f"{safe_model_name}_{req_id}")
            shutil.copytree(os.path.join(work_dir, "output"), adapter_dest, dirs_exist_ok=True)
            archive_dir = os.path.join(ARCHIVE_ROOT, f"run_{req_id}")
            shutil.copytree(work_dir, archive_dir, dirs_exist_ok=True)

            self.send_callback(callback_url, req_id, "success", adapter_path=adapter_dest)
            task_logger.info("Fine‑tune completed successfully → %s", adapter_dest)

        except Exception as exc:
            err_msg = str(exc)
            if task_logger:
                task_logger.exception(f"Fine‑tune failed: {err_msg}")
            else:
                self.logger.exception(f"Fine‑tune failed: {err_msg}")
            if callback_url and req_id:
                self.send_callback(callback_url, req_id, "fail", error=err_msg)
            archive_run("_error")
        finally:
            if work_dir and os.path.exists(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)
            try:
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as exc:
                self.logger.error(f"RabbitMQ ACK failed: {exc}")


def _signal_handler(signum, frame): 
    logging.getLogger("FineTune‑Container").info(f"Signal {signum} caught – shutting down.")
    sys.exit(0)


def main() -> None:
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    processor = FineTuneProcessor()

    connection = pika.BlockingConnection(pika.URLParameters(RABBIT_URL))
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=processor.process_message)

    processor.logger.info("Fine‑tune service (container mode) started – awaiting messages …")
    channel.start_consuming()


if __name__ == "__main__":
    main()
