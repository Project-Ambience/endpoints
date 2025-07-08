import pika
import json

USER_PROMPT_QUEUE = 'user_prompt'
ENGINEERED_PROMPT_QUEUE = 'engineered_prompt'

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

def on_message(ch, method, properties, body):
    msg = json.loads(body)
    orig_prompt = msg['input'][0]['prompt']
    examples = msg.get('examples', [])

    # Generate engineered prompt
    engineered_prompt = format_few_shot_prompt(examples, orig_prompt)

    # Update the prompt in message
    msg['input'][0]['prompt'] = engineered_prompt

    # Publish to engineered_prompt queue
    ch.basic_publish(
        exchange='',
        routing_key=ENGINEERED_PROMPT_QUEUE,
        body=json.dumps(msg)
    )
    ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue=USER_PROMPT_QUEUE)
    channel.queue_declare(queue=ENGINEERED_PROMPT_QUEUE)

    channel.basic_consume(
        queue=USER_PROMPT_QUEUE,
        on_message_callback=on_message
    )
    print('Prompt Engineering Service is running...')
    channel.start_consuming()

if __name__ == '__main__':
    main()
