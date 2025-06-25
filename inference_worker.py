import pika
import json
import argparse
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline as hf_pipeline
import torch

class InferenceHandler:
    def __init__(self, model_path, device):
        self.model_path = model_path
        self.device = device

    def infer(self, prompt):
        raise NotImplementedError()

class VanillaLLMHandler(InferenceHandler):
    """For most Hugging Face causal LLMs with AutoModelForCausalLM"""
    def __init__(self, model_path, device):
        super().__init__(model_path, device)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            device_map=device,
            torch_dtype=torch.bfloat16,
        )
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)

    def infer(self, prompt):
        # Handles plain string prompts (no chat template)
        input_ids = self.tokenizer(prompt, return_tensors="pt").input_ids.to(self.device)
        output = self.model.generate(input_ids=input_ids, max_new_tokens=512)
        result = self.tokenizer.decode(output[0, input_ids.shape[1]:], skip_special_tokens=True)
        return result

class PipelineHandler(InferenceHandler):
    """For models that prefer HF pipeline, e.g., Med42, Llama-3 variants"""
    def __init__(self, model_path, device):
        super().__init__(model_path, device)
        self.pipe = hf_pipeline(
            "text-generation",
            model=model_path,
            torch_dtype=torch.bfloat16,
            device_map=device,
        )
        self.tokenizer = self.pipe.tokenizer

    def infer(self, prompt):
        # Expects prompt as a string (already formatted if multi-turn)
        outputs = self.pipe(
            prompt,
            max_new_tokens=512,
            do_sample=True,
            temperature=0.4,
            top_k=150,
            top_p=0.75,
        )
        # The pipeline returns a list of dicts: [{'generated_text': ...}]
        # We return the generated text after the prompt (like Med42 example)
        generated = outputs[0]["generated_text"]
        return generated[len(prompt):] if generated.startswith(prompt) else generated


HANDLER_REGISTRY = {
    "vanilla": VanillaLLMHandler,
    "pipeline": PipelineHandler,
    # Add more model types as needed
}

def get_handler(model_type, model_path, device):
    handler_cls = HANDLER_REGISTRY.get(model_type)
    if handler_cls is None:
        raise ValueError(f"No handler registered for type: {model_type}")
    return handler_cls(model_path, device)

def main():
    parser = argparse.ArgumentParser(description="Flexible LLM RabbitMQ Inference Worker")
    parser.add_argument("--model-path", type=str, required=True, help="Model path or repo name")
    parser.add_argument("--model-type", type=str, required=True, choices=list(HANDLER_REGISTRY.keys()), help="Type of handler to use for this model")
    parser.add_argument("--rabbitmq-host", type=str, default="localhost", help="RabbitMQ hostname")
    parser.add_argument("--input-queue", type=str, default="inference_requests", help="Input queue name")
    parser.add_argument("--output-queue", type=str, default="inference_results", help="Output queue name")
    args = parser.parse_args()

    device = "hpu"

    print(f"Loading handler '{args.model_type}' for model {args.model_path} on device {device} ...")
    handler = get_handler(args.model_type, args.model_path, device)
    print("Handler loaded. Waiting for prompts...")

    def on_message(ch, method, properties, body):
        try:
            message = json.loads(body)
            prompt = message["prompt"]
            print(f"Received prompt: {prompt!r}")
            result = handler.infer(prompt)
            print(f"Result: {result!r}")
            response = {
                "request_id": message.get("request_id"),
                "result": result,
            }
            ch.basic_publish(
                exchange="",
                routing_key=args.output_queue,
                body=json.dumps(response),
            )
            print("Result sent to output queue.")
        except Exception as e:
            print("Error during inference or message handling:", e)
        finally:
            ch.basic_ack(delivery_tag=method.delivery_tag)

    connection = pika.BlockingConnection(pika.ConnectionParameters(host=args.rabbitmq_host))
    channel = connection.channel()
    channel.queue_declare(queue=args.input_queue)
    channel.queue_declare(queue=args.output_queue)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=args.input_queue, on_message_callback=on_message)
    print("Waiting for messages. To exit press CTRL+C")
    channel.start_consuming()

if __name__ == "__main__":
    main()
