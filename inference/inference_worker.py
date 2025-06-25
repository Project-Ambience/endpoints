import pika
import json
from transformers import pipeline as hf_pipeline
import torch

# Med42 Inference Handle
class Med42Handler:
    def __init__(self, model_path, device):
        self.pipe = hf_pipeline(
            "text-generation",
            model=model_path,
            torch_dtype=torch.bfloat16,
            device_map=device,
        )
        self.tokenizer = self.pipe.tokenizer

    def infer(self, prompt):
        # For Med42, prompt should be a string (multi-turn prompt up to user)
        outputs = self.pipe(
            prompt,
            max_new_tokens=512,
            do_sample=True,
            temperature=0.4,
            top_k=150,
            top_p=0.75,
        )
        generated = outputs[0]["generated_text"]
        return generated[len(prompt):] if generated.startswith(prompt) else generated

def main():
    model_path = "m42-health/Llama3-Med42-8B"
    device = "hpu"

    print(f"Loading Med42 model from {model_path} on device {device} ...")
    handler = Med42Handler(model_path, device)
    print("Model loaded. Waiting for prompts...")

    # RabbitMQ details (guest/guest, host: rabbitmq, port: 5672)
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
