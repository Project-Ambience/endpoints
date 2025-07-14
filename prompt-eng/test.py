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

# Message payload format
message = {
    "conversation_id": "test-123",
    "input": [{
        "prompt": "What are the symptoms of diabetes?"
    }],
    "examples": [
        {"question": "What are the symptoms of flu?", "answer": "Fever, cough, sore throat."},
        {"question": "What are the symptoms of hypertension?", "answer": "Headache, dizziness, and nosebleeds."}
    ]
}

channel.basic_publish(
    exchange='',
    routing_key=input_queue,
    body=json.dumps(message)
)

print("Test prompt sent.")
connection.close()

