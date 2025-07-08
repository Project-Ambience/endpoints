import pika
import json


def format_few_shot_prompt(examples, prompt):
    if examples and len(examples) > 0:
        few_shot_section = ""
        for ex in examples:
            few_shot_section += f"Q: {ex['input']}\nA: {ex['output']}\n\n"
        engineered = f"{few_shot_section}Q: {prompt}\nA: Let's think step by step."
    else:
        # Zero-shot CoT
        engineered = f"{prompt}\nLet's think step by step."
    return engineered


def main():
    # RabbitMQ details
    rabbitmq_host = "128.16.12.219"
    rabbitmq_port = 5672
    rabbitmq_user = "guest"
    rabbitmq_pass = "guest"
    input_queue = "user_prompts"
    output_queue = 'engineered_prompt'

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

    def on_message(ch, method, properties, body):
        try:
            msg = json.loads(body)
            orig_prompt = msg['input'][0]['prompt']
            examples = msg.get('examples', [])

            # Generate engineered prompt
            engineered_prompt = format_few_shot_prompt(examples, orig_prompt)
            print(f"Original prompt: {orig_prompt}")
            print(f"Engineered prompt:\n{engineered_prompt}")

            # Update the prompt in message
            msg['input'][0]['prompt'] = engineered_prompt

            # Remove examples from the message
            if 'examples' in msg:
                del msg['examples']

            # Publish to engineered_prompt queue
            ch.basic_publish(
                exchange='',
                routing_key=output_queue,
                body=json.dumps(msg)
            )
            print(f"Published engineered prompt for conversation_id={msg.get('conversation_id')} to {output_queue}.")
        except Exception as e:
            print("Error processing message:", e)
        finally:
            ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(
        queue=input_queue,
        on_message_callback=on_message
    )
    print('Prompt Engineering Service is running...')
    channel.start_consuming()

if __name__ == '__main__':
    main()
