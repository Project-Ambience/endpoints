import pika
import json
from transformers import pipeline as hf_pipeline, AutoModelForCausalLM, AutoTokenizer
import torch

# PipelineHandler: for Med42, Llama, Mistral, etc.
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

# ChatHandler: for Granite 3.3 Instruct and similar chat/instruct models
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
            # No sampling for most instruct models (greedy by default)
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

def needs_chat_handler(model_path):
    # Use ChatHandler for instruct/chat models (like Granite 3.3 Instruct)
    return "instruct" in model_path.lower() or "chat" in model_path.lower()

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
            if needs_chat_handler(model_path):
                handler_cache[key] = ChatHandler(model_path, device)
            else:
                handler_cache[key] = PipelineHandler(model_path, device)
        return handler_cache[key]

    def on_message(ch, method, properties, body):
        try:
            message = json.loads(body)
            prompt = message["prompt"]
            model_path = message.get("model_path", "ibm-granite/granite-3.3-8b-instruct") 
            device = message.get("device", "hpu")
            handler = get_handler(model_path, device)
            # Use handler's defaults unless message overrides
            generation_args = message.get("generation_args", handler.default_generation_args)

            print(f"Received prompt for model: {model_path}")
            result = handler.infer(prompt, **generation_args)
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
