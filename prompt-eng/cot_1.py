from typing import List, Dict, Optional
from transformers import pipeline
import pika
import json

### some code here to load the user input and model they selected




## if selected_model == "Med42":
      ## import med42 from ...



def few_shot_cot_template(task_instruction: str, examples: List[Dict[str, str]], speciality: str,  model: str = "a medical model") -> str:
    if speciality is not None:
        prompt = f"You are a helpful medical assistant using {model} that specialises in {speciality}. Use step-by-step reasoning.\n\n"

    else:
        prompt = f"You are a helpful medical assistant using {model}. Use step-by-step reasoning.\n\n"
    for i, ex in enumerate(examples, 1):
        prompt += f"Example {i}:\n"
        prompt += f"Question: {ex['input']}\n"
        prompt += f"Answer: {ex['output']}\n\n"
    prompt += "Now answer the following:\n"
    prompt += f"Q: {task_instruction}\n"
    prompt += "A: Let's think step by step."
    return prompt


def few_shot(task_instruction: str, examples: List[Dict[str, str]]) -> str:
    for i, ex in enumerate(examples, 1):
        prompt += f"Example {i}:\n"
        prompt += f"Question: {ex['input']}\n"
        prompt += f"Answer: {ex['output']}\n\n"
    prompt += "Now answer the following:\n"
    prompt += f"Q: {task_instruction}\n"
    prompt += "A: Let's think step by step."
    return prompt


def zero_shot(task_description: str, speciality: str, input_text: str) -> str:
    """
    Create a zero-shot prompt.

    Args:
        task_description (str): What you want the model to do (for example, "Translate to French").
        input_text (str): The actual input to apply the task on.

    Returns:
        str: A zero-shot formatted prompt.
    """
    if speciality is not None:
        prompt = "Lets think this through step by step, you are a medical model specialising in {speciality}" + "\n"

    else:
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
    rag_queue = 'raq_prompt'
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
    channel.queue_declare(queue=rag_queue, durable=True)

    def on_message(ch, method, properties, body):
        try:
            msg = json.loads(body)

            input_messages = msg.get("input", [])
            file_url = msg.get("file_url")
            few_shot_template = msg.get("few_shot_template")
            base_model_path = msg.get("base_model_path")
            adapter_path = msg.get("adapter_path")
            speciality = msg.get("speciality")
            cot = msg.get("CoT")
            few_shot = msg.get("few_shot")
            rag = msg.get("RAG")

            # Extract the first user prompt
            orig_prompt = None
            for m in input_messages:
                if m.get("role") == "user":
                    orig_prompt = m.get("content")
                    break

            if not orig_prompt:
                print("No user prompt found.")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            # Apply prompt engineering
            if few_shot:
                examples = few_shot_template.get("examples", [])
                model_name = msg.get("model", "a medical model")
                if cot:
                    new_prompt = few_shot_cot_template(orig_prompt, examples, speciality, model=model_name)

                new_prompt = few_shot(orig_prompt, examples)

            elif cot:
                new_prompt = zero_shot("Answer the question", speciality, orig_prompt)
                
            else:
                new_prompt = orig_prompt

            # Modify message: update first user message content
            for m in msg["input"]:
                if m.get("role") == "user":
                    m["content"] = new_prompt
                    break


            # Send updated message to output queue
            if rag:
                ch.basic_publish(
                        exchange='',
                        routing_key='rag_prompt',
                        body=json.dumps(msg)
                        )
            else:
                ch.basic_publish(
                        exchange='',
                        routing_key='engineered_prompt',
                        body=json.dumps(msg)
                        )
            print(f"✅ Processed and published for conversation_id={msg.get('conversation_id')}")
        except Exception as e:
            print("❌ Error processing message:", e)
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
