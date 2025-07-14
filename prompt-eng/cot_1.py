from typing import List, Dict, Optional
from transformers import pipeline
import pika
import json

### some code here to load the user input and model they selected




## if selected_model == "Med42":
      ## import med42 from ...




def few_shot_cot_template(task_instruction: str, examples: List[Dict[str, str]]) -> str:
    prompt = f"You are a helpful medical assistant specialising in... Use step-by-step reasoning.\n\n"
    for i, ex in enumerate(examples, 1):
        prompt += f"Example {i}:\n"
        prompt += f"Question: {ex['question']}\n"
        prompt += f"Answer: {ex['answer']}\n\n"
    prompt += "Now answer the following:\n"
    prompt += f"Q: {task_instruction}\n"
    prompt += "A: Let's think step by step.\n"
    return prompt


def zero_shot(task_description: str, input_text: str) -> str:
    """
    Create a zero-shot prompt.

    Args:
        task_description (str): What you want the model to do (for example, "Translate to French").
        input_text (str): The actual input to apply the task on.

    Returns:
        str: A zero-shot formatted prompt.
    """
    prompt = "Lets think this through step by step" + "\n"
    return prompt + f"{task_description}:\n{input_text}\n"


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

            if len(examples) > 0:
                new_prompt = few_shot_cot_template(orig_prompt, examples)

            else:
                new_prompt = zero_shot(orig_prompt[0], orig_prompt[-1]) 


            print(f"Original prompt: {orig_prompt}")
            print(f"Engineered prompt:\n{new_prompt}")

            # Update the prompt in message
            msg['input'][0]['prompt'] = new_prompt

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
