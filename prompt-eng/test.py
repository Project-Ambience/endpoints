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

# New message format
message = {
    "conversation_id": "test-123",
    "file_url": "http://example.com/input.txt",
    "few_shot_template": [
        {
            "name": "Symptom Explainer",
            "description": "Medical reasoning template",
            "examples": [
                {"input": "What are the symptoms of flu?", "output": "Fever, cough, sore throat."},
                {"input": "What are the symptoms of hypertension?", "output": "Headache, dizziness, and nosebleeds."}
            ]
        }
    ],
    "input": [
        {"role": "user", "content": "What are the symptoms of diabetes?"}
    ],
    "base_model_path": "/models/med42",
    "adapter_path": "/models/adapters/med42-lora",
    "speciality": "cancer"
}

channel.basic_publish(
    exchange='',
    routing_key=input_queue,
    body=json.dumps(message)
)

print("✅ Test prompt sent.")
connection.close()

