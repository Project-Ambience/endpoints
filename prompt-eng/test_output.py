import pika
import json

rabbitmq_host = "128.16.12.219"
rabbitmq_port = 5672
rabbitmq_user = "guest"
rabbitmq_pass = "guest"
output_queue = "engineered_prompt"

credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_pass)
connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=rabbitmq_host,
        port=rabbitmq_port,
        credentials=credentials
    )
)
channel = connection.channel()
channel.queue_declare(queue=output_queue, durable=True)

def callback(ch, method, properties, body):
    print("✅ Received from output queue:")
    print(json.dumps(json.loads(body), indent=2))
    ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_consume(queue=output_queue, on_message_callback=callback)
print("📥 Listening to 'engineered_prompt' queue...")
channel.start_consuming()

