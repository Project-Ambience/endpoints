import pika
import json

rabbitmq_host = "128.16.12.219"
rabbitmq_port = 5672
rabbitmq_user = "guest"
rabbitmq_pass = "guest"

queues_to_listen = ["engineered_prompt", "rag_prompt"]

credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_pass)
connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=rabbitmq_host,
        port=rabbitmq_port,
        credentials=credentials
    )
)
channel = connection.channel()

for queue in queues_to_listen:
    channel.queue_declare(queue=queue, durable=True)

    def make_callback(queue_name):
        def callback(ch, method, properties, body):
            print(f"\n✅ Received from '{queue_name}' queue:")
            print(json.dumps(json.loads(body), indent=2))
            ch.basic_ack(delivery_tag=method.delivery_tag)
        return callback

    channel.basic_consume(queue=queue, on_message_callback=make_callback(queue))

print("📥 Listening to 'engineered_prompt' and 'rag_prompt' queues...")
channel.start_consuming()

