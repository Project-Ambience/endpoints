#!/usr/bin/env python3
import os
import sys
import json
import pika
import shutil
import tempfile
import requests
import logging
import subprocess
from pathlib import Path
from transformers import AutoModel, AutoTokenizer


RABBIT_URL = os.environ.get("RABBIT_URL", "amqp://guest:guest@128.16.12.219:5672/")
QUEUE_NAME = os.environ.get("QUEUE_NAME", "fine_tune_requests")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
root_logger = logging.getLogger()

archive_root = "/app/endpoints/fine-tuning/finetune_runs"
os.makedirs(archive_root, exist_ok=True)

# Default DeepSpeed config path - can be overridden in parameters
DEFAULT_DEEPSPEED_CONFIG = "/app/optimum-habana/examples/language-modeling/llama3_ds_zero1_config.json"


def get_model_target_modules(model_path, task_logger):
    """
    Inspect the model to find the correct target modules for LoRA.
    """
    try:
        # Load model to inspect layer names
        model = AutoModel.from_pretrained(model_path, trust_remote_code=True)
        
        # Common patterns for different model architectures
        target_modules = []
        
        # Look for attention projection layers
        for name, module in model.named_modules():
            if any(pattern in name for pattern in ['q_proj', 'v_proj', 'k_proj', 'o_proj', 
                                                   'query', 'value', 'key', 'dense']):
                # Extract the layer type (e.g., 'q_proj' from 'model.layers.0.self_attn.q_proj')
                layer_name = name.split('.')[-1]
                if layer_name not in target_modules:
                    target_modules.append(layer_name)
        
        # Default fallback based on common architectures
        if not target_modules:
            # Try common Llama/Mistral patterns
            common_targets = ['q_proj', 'v_proj', 'k_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj']
            for target in common_targets:
                for name, _ in model.named_modules():
                    if target in name:
                        target_modules.append(target)
                        break
        
        # Remove duplicates and sort
        target_modules = sorted(list(set(target_modules)))
        
        if target_modules:
            task_logger.info(f"Found target modules: {target_modules}")
            return target_modules
        else:
            # Last resort defaults
            default_targets = ['q_proj', 'v_proj']
            task_logger.warning(f"No target modules found, using defaults: {default_targets}")
            return default_targets
            
    except Exception as e:
        task_logger.error(f"Error inspecting model: {e}")
        # Return safe defaults
        return ['q_proj', 'v_proj']


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
        params = json.loads(raw_params) if isinstance(raw_params, str) else raw_params
        task_logger.info(f"Parsed fine-tuning parameters: {params}")
    except Exception as e:
        params = {}
        task_logger.warning(f"Failed to parse parameters JSON, using defaults: {e}")

    # Create data directory and files
    data_dir = os.path.join(work_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    # Create train and validation files
    train_file = os.path.join(data_dir, f"train_{req_id}.json")
    val_file = os.path.join(data_dir, f"val_{req_id}.json")
    
    # Split data into train/val if not already split
    if len(examples) > 1:
        split_idx = int(len(examples) * 0.9)  # 90% train, 10% val
        train_data = examples[:split_idx]
        val_data = examples[split_idx:]
    else:
        train_data = examples
        val_data = examples  # Use same data for validation if only one example
    
    with open(train_file, "w") as f:
        json.dump(train_data, f, indent=2)
    with open(val_file, "w") as f:
        json.dump(val_data, f, indent=2)
    
    task_logger.info(f"Wrote {len(train_data)} train examples and {len(val_data)} validation examples")

    # Output directory
    output_dir = os.path.join(work_dir, "out")
    os.makedirs(output_dir, exist_ok=True)

    # Get target modules for the specific model
    target_modules = get_model_target_modules(model_path, task_logger)
    
    # Default configuration with your optimized settings
    default_config = {
        "world_size": 4,
        "num_train_epochs": 3,
        "per_device_train_batch_size": 1,
        "per_device_eval_batch_size": 1,
        "gradient_accumulation_steps": 16,
        "save_strategy": "no",
        "eval_strategy": "epoch",
        "eval_steps": 50,
        "learning_rate": 5e-5,
        "warmup_ratio": 0.1,
        "lr_scheduler_type": "linear",
        "max_grad_norm": 1.0,
        "logging_steps": 10,
        "lora_rank": 8,
        "lora_alpha": 16,
        "lora_dropout": 0.05,
        "lora_target_modules": target_modules,
        "max_seq_length": 2048,
        "adam_epsilon": 1e-08,
        "deepspeed_config": DEFAULT_DEEPSPEED_CONFIG,
        "cache_size_limit": 64
    }
    
    # Update with user-provided parameters
    config = {**default_config, **params}
    
    task_logger.info(f"Final training config: {config}")

    # Build the command
    cmd = [
        "python", "/app/optimum-habana/examples/gaudi_spawn.py",
        "--world_size", str(config.get("world_size", 4)),
        "--use_deepspeed",
        "/app/optimum-habana/examples/language-modeling/run_lora_clm.py",
        "--model_name_or_path", model_path,
        "--train_file", train_file,
        "--validation_file", val_file,
        "--do_train",
        "--do_eval",
        "--bf16", "True",
        "--output_dir", output_dir,
        "--num_train_epochs", str(config.get("num_train_epochs", 3)),
        "--per_device_train_batch_size", str(config.get("per_device_train_batch_size", 1)),
        "--per_device_eval_batch_size", str(config.get("per_device_eval_batch_size", 1)),
        "--gradient_accumulation_steps", str(config.get("gradient_accumulation_steps", 16)),
        "--save_strategy", config.get("save_strategy", "no"),
        "--eval_strategy", config.get("eval_strategy", "epoch"),
        "--eval_steps", str(config.get("eval_steps", 50)),
        "--learning_rate", str(config.get("learning_rate", 5e-5)),
        "--warmup_ratio", str(config.get("warmup_ratio", 0.1)),
        "--lr_scheduler_type", config.get("lr_scheduler_type", "linear"),
        "--max_grad_norm", str(config.get("max_grad_norm", 1.0)),
        "--logging_steps", str(config.get("logging_steps", 10)),
        "--use_habana",
        "--use_lazy_mode", "False",
        "--throughput_warmup_steps", "3",
        "--lora_rank", str(config.get("lora_rank", 8)),
        "--lora_alpha", str(config.get("lora_alpha", 16)),
        "--lora_dropout", str(config.get("lora_dropout", 0.05)),
        "--max_seq_length", str(config.get("max_seq_length", 2048)),
        "--adam_epsilon", str(config.get("adam_epsilon", 1e-08)),
        "--deepspeed", config.get("deepspeed_config", DEFAULT_DEEPSPEED_CONFIG),
        "--torch_compile_backend", "hpu_backend",
        "--torch_compile",
        "--fp8",
        "--use_flash_attention", "True",
        "--flash_attention_causal_mask", "True",
        "--cache_size_limit", str(config.get("cache_size_limit", 64)),
        "--use_regional_compilation",
        "--compile_from_sec_iteration",
        "--allow_unspec_int_on_nn_module", "True"
    ]
    
    # Add target modules (can be multiple)
    for module in config.get("lora_target_modules", target_modules):
        cmd.extend(["--lora_target_modules", module])

    # Set environment variables
    env = os.environ.copy()
    env.update({
        "PT_TE_CUSTOM_OP": "1",
        "PT_HPU_LAZY_MODE": "0"
    })

    try:
        task_logger.info("Starting Intel Gaudi fine-tuning...")
        task_logger.info(f"Command: {' '.join(cmd)}")
        
        # Run the fine-tuning command
        result = subprocess.run(
            cmd,
            cwd=work_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=7200  # 2 hour timeout
        )
        
        # Log the output
        task_logger.info(f"Fine-tuning stdout:\n{result.stdout}")
        if result.stderr:
            task_logger.info(f"Fine-tuning stderr:\n{result.stderr}")
        
        if result.returncode == 0:
            task_logger.info("Fine-tuning completed successfully.")
        else:
            status = "fail"
            error = f"Fine-tuning failed with return code {result.returncode}: {result.stderr}"
            task_logger.error(error)
            
    except subprocess.TimeoutExpired:
        status = "fail"
        error = "Fine-tuning timed out after 2 hours"
        task_logger.error(error)
    except Exception as e:
        status = "fail"
        error = f"Fine-tuning failed: {str(e)}"
        task_logger.exception("Fine-tuning failed:")
    finally:
        # Send callback
        _send_callback(callback_url, req_id, status, error, task_logger)
        
        # Archive the results
        archive_dir = os.path.join(archive_root, f"run_{req_id}")
        shutil.copytree(work_dir, archive_dir, dirs_exist_ok=True)
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