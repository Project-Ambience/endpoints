import pika
import json

# RabbitMQ connection details
rabbitmq_host = "128.16.12.219"
rabbitmq_port = 5672
rabbitmq_user = "guest"
rabbitmq_pass = "guest"
input_queue = "user_prompts"

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

# Zero-shot message format
message = {
    "conversation_id": "test-456",
    "file_url": None,
    "few_shot_template": None,
    "input": [
        {"role": "user", "content": "What causes high blood pressure?"}
    ],
    "base_model_path": "/models/med42",
    "adapter_path": "/models/adapters/med42-lora"
}

channel.basic_publish(
    exchange='',
    routing_key=input_queue,
    body=json.dumps(message)
)

print("✅ Zero-shot test prompt sent.")
connection.close()

