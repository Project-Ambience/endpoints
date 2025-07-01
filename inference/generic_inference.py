import os
os.environ["HF_HOME"] = "/models"

import pika
import json
from transformers import pipeline as hf_pipeline, AutoModelForCausalLM, AutoTokenizer, AutoProcessor, AutoModelForVision2Seq
import transformers
print("Transformers cache dir:", transformers.utils.default_cache_path)
import torch
import mimetypes

HF_CACHE_PREFIX = "/models"

def is_image_file(filepath):
    mime, _ = mimetypes.guess_type(filepath)
    return mime is not None and mime.startswith("image")

def is_text_file(filepath):
    mime, _ = mimetypes.guess_type(filepath)
    return mime is not None and mime.startswith("text")

def parse_input(input_list, is_vision_model=False): 
    user_prompt = ""
    file_text = None
    file_path = None

    for item in input_list:
        if "prompt" in item:
            user_prompt = item["prompt"]
        if "file" in item:
            file_path = item["file"]

    if file_path:
        if is_vision_model and is_image_file(file_path):
            # For vision models: return multimodal chat format
            return [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "url": file_path},
                        {"type": "text", "text": user_prompt}
                    ]
                }
            ]
        elif not is_vision_model and is_text_file(file_path):
            # For text models: append file contents to prompt
            try:
                with open(file_path, "r") as f:
                    file_text = f.read()
            except Exception as e:
                print(f"Error reading file {file_path}: {e}")
                file_text = ""
            return user_prompt + "\n" + file_text if file_text else user_prompt

    # Default: return user prompt
    return user_prompt

class PipelineHandler:
    def __init__(self, model_path, device):
        self.pipe = hf_pipeline(
            "text-generation",
            model=model_path,
            torch_dtype=torch.bfloat16,
            device_map=device,
        )
        self.tokenizer = self.pipe.tokenizer

    @property
    def default_generation_args(self):
        return {
            "max_new_tokens": 512,
            "do_sample": True,
            "temperature": 0.4,
            "top_k": 150,
            "top_p": 0.75,
        }

    def infer(self, prompt, **generation_args):
        # Use handler's defaults if not specified
        if not generation_args:
            generation_args = self.default_generation_args
        outputs = self.pipe(prompt, **generation_args)
        generated = outputs[0]["generated_text"]
        return generated[len(prompt):] if generated.startswith(prompt) else generated

class ChatHandler:
    def __init__(self, model_path, device):
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.bfloat16,
            device_map=device,
        )
        self.device = device

    @property
    def default_generation_args(self):
        return {
            "max_new_tokens": 512, 
        }

    def infer(self, prompt, **generation_args):
        if not generation_args:
            generation_args = self.default_generation_args
        eos_token_id = self.tokenizer.eos_token_id
        generation_args.setdefault("pad_token_id", eos_token_id)
        generation_args.setdefault("eos_token_id", eos_token_id)
        if isinstance(prompt, str):
            prompt = [{"role": "user", "content": prompt}]
        inputs = self.tokenizer.apply_chat_template(
            prompt,
            return_tensors="pt",
            return_dict=True,
            add_generation_prompt=True
        )
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        outputs = self.model.generate(
            input_ids=inputs["input_ids"],
            attention_mask=inputs.get("attention_mask"),
            **generation_args
        )
        result = self.tokenizer.decode(
            outputs[0, inputs["input_ids"].shape[1]:],
            skip_special_tokens=True
        )
        return result

class VisionHandler:
    def __init__(self, model_path, device):
        self.processor = AutoProcessor.from_pretrained(model_path)
        self.model = AutoModelForVision2Seq.from_pretrained(model_path).to(device)
        self.device = device

    @property
    def default_generation_args(self):
        return {
            "max_new_tokens": 100,
        }

    def infer(self, prompt, **generation_args):
        # prompt is the conversation format (list of dicts)
        inputs = self.processor.apply_chat_template(
            prompt,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt"
        ).to(self.device)
        output = self.model.generate(**inputs, **generation_args)
        return self.processor.decode(output[0], skip_special_tokens=True)

def needs_chat_handler(model_path):
    return "instruct" in model_path.lower() or "chat" in model_path.lower()

def is_vision_handler(model_path):
    return "vision" in model_path.lower()

def main():
    # RabbitMQ details
    rabbitmq_host = "128.16.12.219"
    rabbitmq_port = 5672
    rabbitmq_user = "guest"
    rabbitmq_pass = "guest"
    input_queue = "user_prompts"
    output_queue = "inference_results"

    credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_pass)
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=rabbitmq_host,
            port=rabbitmq_port,
            credentials=credentials
        )
    )
    channel = connection.channel()
    channel.queue_declare(queue=input_queue, durable=True)
    channel.queue_declare(queue=output_queue, durable=True)
    channel.basic_qos(prefetch_count=1)

    handler_cache = {}

    def get_handler(model_path, device):
        key = (model_path, device)
        if key not in handler_cache:
            print(f"Loading model: {model_path} on {device}")
            if is_vision_handler(model_path):
                handler_cache[key] = VisionHandler(model_path, device)
            elif needs_chat_handler(model_path):
                handler_cache[key] = ChatHandler(model_path, device)
            else:
                handler_cache[key] = PipelineHandler(model_path, device)
        return handler_cache[key]

    def on_message(ch, method, properties, body):
        try:
            message = json.loads(body)
            input_list = message["input"]
            model_path = message["model_path"]
            device = "hpu"
            handler = get_handler(model_path, device)

            if is_vision_handler(model_path):
                parsed_prompt = parse_input(input_list, is_vision_model=True)
            else:
                parsed_prompt = parse_input(input_list, is_vision_model=False)
            
            # Use handler's defaults unless message overrides
            generation_args = message.get("generation_args", handler.default_generation_args)
            print(f"Received prompt for model: {model_path}")
            result = handler.infer(parsed_prompt, **generation_args)
            print(f"Result: {result!r}")

            response = {
                "conversation_id": message.get("conversation_id"),
                "result": result,
            }
            ch.basic_publish(
                exchange="",
                routing_key=output_queue,
                body=json.dumps(response),
            )
            print("Result sent to output queue")
        except Exception as e:
            print("Error during inference or message handling:", e)
        finally:
            ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=input_queue, on_message_callback=on_message)
    print("Waiting for messages. To exit press CTRL+C")
    channel.start_consuming()

if __name__ == "__main__":
    main()
