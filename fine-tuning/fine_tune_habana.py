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
import traceback
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from transformers import AutoConfig, AutoTokenizer
import time
import signal


RABBIT_URL = os.environ.get("RABBIT_URL", "amqp://guest:guest@128.16.12.219:5672/?heartbeat=0")
QUEUE_NAME = os.environ.get("QUEUE_NAME", "model_fine_tune_requests")
ARCHIVE_ROOT = os.environ.get("ARCHIVE_ROOT", "/app/endpoints/fine-tuning/finetune_runs")
MODELS_ROOT = os.environ.get("MODELS_ROOT", "/models")
DEFAULT_DEEPSPEED_CONFIG = os.environ.get(
    "DEEPSPEED_CONFIG", 
    "/app/optimum-habana/examples/language-modeling/llama3_ds_zero1_config.json"
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


class FineTuneProcessor:    
    def __init__(self):
        self.setup_logging()
        self.ensure_directories()
        
    def setup_logging(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(os.path.join(LOG_DIR, "fine_tune_service.log"), mode='a')
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def ensure_directories(self):
        directories = [ARCHIVE_ROOT, MODELS_ROOT, LOG_DIR]
        for directory in directories:
            try:
                os.makedirs(directory, exist_ok=True)
                self.logger.info(f"Ensured directory exists: {directory}")
            except PermissionError:
                self.logger.warning(f"No permission to create directory: {directory}")
            except Exception as e:
                self.logger.error(f"Failed to create directory {directory}: {e}")
            
    def get_model_info(self, model_path: str) -> Tuple[str, List[str]]:
        try:
            model_name = Path(model_path).name.lower()
            safe_model_name = "".join(c if c.isalnum() or c in '-_' else '_' for c in model_name)
            
            config = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
            model_type = getattr(config, 'model_type', 'unknown').lower()
            
            target_modules_map = {
                'llama': ['q_proj', 'v_proj', 'k_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'],
                'mistral': ['q_proj', 'v_proj', 'k_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'],
                'gemma': ['q_proj', 'v_proj', 'k_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'],
                'qwen': ['q_proj', 'v_proj', 'k_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'],
                'phi': ['q_proj', 'v_proj', 'dense', 'fc1', 'fc2'],
                'gpt': ['c_attn', 'c_proj', 'c_fc'],
                'bert': ['query', 'key', 'value', 'dense'],
                'roberta': ['query', 'key', 'value', 'dense'],
            }
            
            target_modules = target_modules_map.get(model_type, ['q_proj', 'v_proj', 'k_proj', 'o_proj'])
            
            self.logger.info(f"Detected model type: {model_type}, using target modules: {target_modules}")
            return safe_model_name, target_modules
            
        except Exception as e:
            self.logger.warning(f"Could not determine model architecture: {e}")
            safe_model_name = "unknown_model"
            target_modules = ['q_proj', 'v_proj']
            return safe_model_name, target_modules
            
    def validate_message(self, msg: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        required_fields = ["fine_tune_request_id", "ai_model_path", "callback_url"]
        
        for field in required_fields:
            if field not in msg:
                return False, f"Missing required field: {field}"
                
        if not isinstance(msg.get("fine_tune_data", []), list):
            return False, "fine_tune_data must be a list"
            
        if len(msg.get("fine_tune_data", [])) == 0:
            return False, "fine_tune_data cannot be empty"
            
        return True, None
        
    def prepare_training_data(self, examples: List[Dict], data_dir: str, req_id: str) -> Tuple[str, str]:
    
        train_file = os.path.join(data_dir, f"train_{req_id}.json")
        val_file = os.path.join(data_dir, f"val_{req_id}.json")
        
        for i, example in enumerate(examples):
            if not isinstance(example, dict):
                raise ValueError(f"Example {i} is not a dictionary")
            if "input" not in example and "text" not in example:
                self.logger.warning(f"Example {i} missing 'input' or 'text' field")
        
        if len(examples) > 1:
            split_idx = max(1, int(len(examples) * 0.9))  
            train_data = examples[:split_idx]
            val_data = examples[split_idx:]
        else:
            train_data = examples
            val_data = examples  
        
        with open(train_file, "w", encoding='utf-8') as f:
            json.dump(train_data, f, indent=2, ensure_ascii=False)
        with open(val_file, "w", encoding='utf-8') as f:
            json.dump(val_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Created training data: {len(train_data)} train, {len(val_data)} validation examples")
        return train_file, val_file
        
    def build_training_command(self, config: FineTuneConfig, model_path: str, 
                             train_file: str, val_file: str, output_dir: str,
                             target_modules: List[str]) -> List[str]:
       
        cmd = [
            "python", "/app/optimum-habana/examples/gaudi_spawn.py",
            "--world_size", str(config.world_size),
            "--use_deepspeed",
            "/app/optimum-habana/examples/language-modeling/run_lora_clm.py",
            "--model_name_or_path", model_path,
            "--train_file", train_file,
            "--validation_file", val_file,
            "--do_train",
            "--do_eval",
            "--bf16", "True",
            "--output_dir", output_dir,
            "--num_train_epochs", str(config.num_train_epochs),
            "--per_device_train_batch_size", str(config.per_device_train_batch_size),
            "--per_device_eval_batch_size", str(config.per_device_eval_batch_size),
            "--gradient_accumulation_steps", str(config.gradient_accumulation_steps),
            "--save_strategy", config.save_strategy,
            "--eval_strategy", config.eval_strategy,
            "--eval_steps", str(config.eval_steps),
            "--learning_rate", str(config.learning_rate),
            "--warmup_ratio", str(config.warmup_ratio),
            "--lr_scheduler_type", config.lr_scheduler_type,
            "--max_grad_norm", str(config.max_grad_norm),
            "--logging_steps", str(config.logging_steps),
            "--use_habana",
            "--use_lazy_mode", "False",
            "--throughput_warmup_steps", "3",
            "--lora_rank", str(config.lora_rank),
            "--lora_alpha", str(config.lora_alpha),
            "--lora_dropout", str(config.lora_dropout),
            "--max_seq_length", str(config.max_seq_length),
            "--adam_epsilon", str(config.adam_epsilon),
            "--deepspeed", config.deepspeed_config,
            "--torch_compile_backend", "hpu_backend",
            "--torch_compile",
            "--fp8",
            "--use_flash_attention", "True",
            "--flash_attention_causal_mask", "True",
            "--cache_size_limit", str(config.cache_size_limit),
            "--use_regional_compilation",
            "--compile_from_sec_iteration",
            "--allow_unspec_int_on_nn_module", "True"
        ]
                   
        if target_modules:
            cmd.append("--lora_target_modules")
            for m in target_modules:
                cmd.append(f'"{m}"')

        return cmd
        
    def send_callback(self, url: str, req_id: str, status: str, adapter_path: str, error: Optional[str] = None):
        
        payload = {
            "id": req_id,
            "status": status,
            "adapter_path": adapter_path
        }
        
        if error:
            payload["error"] = error
            
        try:
            response = requests.post(url, json=payload, timeout=CALLBACK_TIMEOUT)
            response.raise_for_status()
            self.logger.info(f"Callback sent successfully: {payload}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to send callback: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error sending callback: {e}")
            
    def process_message(self, ch, method, props, body):
       
        req_id = None
        callback_url = None
        work_dir = None
        task_logger = None
        
        def archive_run(suffix: str = ""):
            run_dir = f"run_{req_id}{suffix}"
            archive_dir = os.path.join(ARCHIVE_ROOT, run_dir)
            try:
                shutil.copytree(work_dir, archive_dir, dirs_exist_ok=True)
                task_logger.info(f"Archived to: {archive_dir}")
            except Exception as e:
                task_logger.warning(f"Failed to archive to {archive_dir}: {e}")
        
        try:
            msg = json.loads(body.decode('utf-8'))
            
            is_valid, error_msg = self.validate_message(msg)
            if not is_valid:
                self.logger.error(f"Invalid message: {error_msg}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return
                
            req_id = msg.get("fine_tune_request_id")    
            model_path = msg.get("ai_model_path")
            raw_params = msg.get("parameters", "{}")
            examples = msg.get("fine_tune_data", [])
            callback_url = msg.get("callback_url")
            
            work_dir = tempfile.mkdtemp(prefix=f"ft_{req_id}_")
            log_file = os.path.join(work_dir, "fine_tune.log")
            task_logger = logging.getLogger(f"finetune_{req_id}")
            task_logger.setLevel(logging.INFO)
            handler = logging.FileHandler(log_file)
            handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
            task_logger.addHandler(handler)
            
            task_logger.info(f"Processing fine-tune request {req_id}")
            task_logger.info(f"Model path: {model_path}")
            task_logger.info(f"Number of examples: {len(examples)}")
            
            try:
                params = json.loads(raw_params) if isinstance(raw_params, str) else raw_params
                task_logger.info(f"User parameters: {params}")
            except json.JSONDecodeError as e:
                params = {}
                task_logger.warning(f"Failed to parse parameters JSON, using defaults: {e}")
                
            safe_model_name, target_modules = self.get_model_info(model_path)
            
            config = FineTuneConfig()
            for key, value in params.items():
                if hasattr(config, key):
                    setattr(config, key, value)
                    task_logger.info(f"Set {key} = {value}")
                    
            if 'lora_target_modules' not in params:
                config.lora_target_modules = target_modules
            else:
                config.lora_target_modules = params['lora_target_modules']
                
            task_logger.info(f"Final config: {config}")
            
            data_dir = os.path.join(work_dir, "data")
            output_dir = os.path.join(work_dir, "output")
            os.makedirs(data_dir, exist_ok=True)
            os.makedirs(output_dir, exist_ok=True)
            
            train_file, val_file = self.prepare_training_data(examples, data_dir, req_id)
            
            
            cmd = self.build_training_command(
                config, model_path, train_file, val_file, output_dir, target_modules
            )
            
            env = os.environ.copy()
            env.update({
                "PT_TE_CUSTOM_OP": "1",
                "PT_HPU_LAZY_MODE": "0",
                "PYTHONUNBUFFERED": "1",
                "HCL_LOG_LEVEL": "DEBUG",
                "PT_HPU_VERBOSE": "1"
            })
            
            task_logger.info("Starting Intel Gaudi fine-tuning (streaming logs)...")
            task_logger.info(f"Command: {' '.join(cmd)}")

            start_time = time.time()
            proc = subprocess.Popen(
                cmd,
                cwd=work_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            for line in proc.stdout:
                task_logger.info(line.rstrip())
            returncode = proc.wait(timeout=FINE_TUNE_TIMEOUT)

            duration = time.time() - start_time
            task_logger.info(f"Fine-tuning finished in {duration:.2f} seconds with exit code {returncode}")

            if returncode != 0:
                error_msg = f"Fine-tuning failed with return code {returncode}"
                task_logger.error(error_msg)
                archive_run(suffix="_fail")
                self.send_callback(callback_url, req_id, "fail", error_msg)
                return


            adapter_path = os.path.join(MODELS_ROOT, f"{safe_model_name}_{req_id}")
            
            checkpoint_dirs = [d for d in os.listdir(output_dir) if d.startswith('checkpoint')]
            if checkpoint_dirs:
                source_checkpoint = os.path.join(output_dir, checkpoint_dirs[-1])  
            else:
                source_checkpoint = output_dir
                
            if os.path.exists(source_checkpoint):
                shutil.copytree(source_checkpoint, adapter_path, dirs_exist_ok=True)
                task_logger.info(f"Adapter saved to: {adapter_path}")
            else:
                shutil.copytree(output_dir, adapter_path, dirs_exist_ok=True)
                task_logger.warning(f"No checkpoint directory found, copied entire output to: {adapter_path}")
                
            archive_dir = os.path.join(ARCHIVE_ROOT, f"run_{req_id}")
            shutil.copytree(work_dir, archive_dir, dirs_exist_ok=True)
            task_logger.info(f"Archived to: {archive_dir}")
            
            self.send_callback(callback_url, req_id, "success", adapter_path=adapter_path)
            task_logger.info("Fine-tuning completed successfully")
            
        except subprocess.TimeoutExpired:
            error_msg = f"Fine-tuning timed out after {FINE_TUNE_TIMEOUT} seconds"
            if task_logger:
                task_logger.error(error_msg)
                archive_run(suffix="_timeout")
            self.send_callback(callback_url, req_id, "fail", error_msg)
            
        except Exception as e:
            error_msg = f"Fine-tuning failed: {str(e)}"
            if task_logger:
                task_logger.exception(f"Fine-tuning failed with exception: {e}")
                archive_run(suffix="_error")
            else:
                self.logger.exception(f"Fine-tuning failed with exception: {e}")
            self.send_callback(callback_url, req_id, "fail", error_msg)
            
        finally:
            if work_dir and os.path.exists(work_dir):
                try:
                    shutil.rmtree(work_dir)
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup work directory {work_dir}: {e}")
                    
            try:
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                self.logger.error(f"Failed to acknowledge message: {e}")


def signal_handler(signum, frame):
    logging.getLogger(__name__).info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    processor = FineTuneProcessor()
    
    try:
        connection = pika.BlockingConnection(pika.URLParameters(RABBIT_URL))
        channel = connection.channel()
        
        channel.queue_declare(queue=QUEUE_NAME, durable=True)
        
        channel.basic_qos(prefetch_count=1)
        
        channel.basic_consume(
            queue=QUEUE_NAME,
            on_message_callback=processor.process_message
        )
        
        processor.logger.info("Fine-tuning service started. Waiting for requests...")
        channel.start_consuming()
        
    except KeyboardInterrupt:
        processor.logger.info("Shutting down...")
        
    except Exception as e:
        processor.logger.exception("Service failed:")
        sys.exit(1)


if __name__ == "__main__":
    main()
    