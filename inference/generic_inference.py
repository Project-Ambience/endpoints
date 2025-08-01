import os
os.environ["HF_HOME"] = "/models"

import pika
import json
from transformers import pipeline as hf_pipeline, AutoModelForCausalLM, AutoTokenizer, AutoProcessor, AutoModelForVision2Seq
import transformers
print("Transformers cache dir:", transformers.utils.default_cache_path)
import torch
import mimetypes
import requests
from io import BytesIO

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

try:
    from peft import PeftModel
except ImportError:
    PeftModel = None

def is_image_file(filepath):
    mime, _ = mimetypes.guess_type(filepath)
    return mime is not None and mime.startswith("image")

def extract_text_from_pdf(file_obj):
    if PdfReader is None:
        print("PyPDF2 not installed, can't extract PDF text")
        return ""
    try:
        reader = PdfReader(file_obj)
        return "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
    except Exception as e:
        print(f"PDF extraction failed: {e}")
        return ""

def compose_prompt(input_list):
    """
    Compose the prompt for the model based on the input conversation history
    If user has rejected a previous response, build a correction prompt
    Otherwise, just use the latest user prompt
    """
    # Find all user and assistant turns
    user_turns = [msg["content"] for msg in input_list if msg["role"] == "user"]
    assistant_turns = [msg["content"] for msg in input_list if msg["role"] == "assistant"]
    
    # Correction case: at least one user, one assistant, and then a user rejection/comment
    if len(user_turns) >= 2 and len(assistant_turns) >= 1:
        original_prompt = user_turns[0]
        rejected_response = assistant_turns[-1]
        rejection_comment = user_turns[-1]
        # Compose correction prompt
        correction_template = (
            "You are an intelligent assistant being trained to improve your responses based on user corrections. "
            "A user has rejected your first answer to their prompt. Your task is to analyse their feedback and provide a superior, corrected answer.\n"
            "1. Original User Prompt: {original}\n"
            "2. Your Rejected Response: {rejected}\n"
            "3. User's Feedback and Reason for Rejection: {feedback}\n\n"
            "Your Instructions:\n"
            "Analyse why your previous response was inadequate based on the user's feedback. Identify the key mistake or omission.\n"
            "Then, provide a new, comprehensive response that fixes the identified issue and fully satisfies the user's original prompt.\n\n"
        )
        return correction_template.format(
            original=original_prompt,
            rejected=rejected_response,
            feedback=rejection_comment
        )
    else:
        # Send latest user message
        for msg in reversed(input_list):
            if msg["role"] == "user":
                return msg["content"]
        # Fallback if no user message found
        return ""
    
def extract_llama3_answer(text):
    if "<|assistant|>" in text:
        return text.split("<|assistant|>")[-1].strip()
    return text.strip()

def parse_input(message, is_vision_model=False): 
    input_list = message.get("input", [])
    file_path = message.get("file_url", None)
    prompt_text = compose_prompt(input_list)
    file_text = None

    if is_vision_model:
        if not file_path or not is_image_file(file_path):
            raise ValueError("No image file provided for vision model. Please upload an image with your prompt.")
        return [
            {
                "role": "user",
                "content": [
                    {"type": "image", "url": file_path},
                    {"type": "text", "text": prompt_text}
                ]
            }
        ]
    elif file_path:
        try:
            if file_path.startswith("http"):
                response = requests.get(file_path)
                response.raise_for_status()
                mime = response.headers.get('Content-Type', '')
                if "pdf" in mime and PdfReader:
                    file_text = extract_text_from_pdf(BytesIO(response.content))
                    print(f"Extracted PDF text (url): {file_text[:100]}")
                elif 'text' in mime:
                    file_text = response.text
                    print(f"Extracted text file (url): {file_text[:100]}")
                else:
                    print(f"Unhandled mime type (url): {mime}")
                    file_text = ""
            else:
                mime, _ = mimetypes.guess_type(file_path)
                if mime and "pdf" in mime and PdfReader:
                    with open(file_path, "rb") as f:
                        file_text = extract_text_from_pdf(f)
                elif mime and "text" in mime:
                    with open(file_path, "r") as f:
                        file_text = f.read()
                else:
                    print(f"Unhandled mime type (local): {mime}")
                    file_text = ""
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            file_text = ""
        return prompt_text + "\n" + (file_text or "")
    else:
        return prompt_text

class PipelineHandler:
    def __init__(self, base_model_path, device, adapter_path=None):
        if adapter_path and PeftModel:
            # Load the base model and then apply the adapter
            self.model = AutoModelForCausalLM.from_pretrained(
                base_model_path,
                torch_dtype=torch.bfloat16,
                device_map=device,
                trust_remote_code=True
            )
            self.model = PeftModel.from_pretrained(
                self.model,
                adapter_path,
                torch_dtype=torch.bfloat16,
                device_map=device
            )
            self.tokenizer = AutoTokenizer.from_pretrained(base_model_path)
        else:
            self.pipe = hf_pipeline(
                "text-generation",
                model=base_model_path,
                torch_dtype=torch.bfloat16,
                device_map=device,
            )
            self.tokenizer = self.pipe.tokenizer
        self.adapter_path = adapter_path
        self.base_model_path = base_model_path
        self.device = device

    @property
    def default_generation_args(self):
        return {
            "max_new_tokens": 512,
            "do_sample": True,
            "temperature": 0.4,
            "top_k": 150,
            "top_p": 0.75,
        }

    def infer(self, prompt, **generation_args):
        if self.adapter_path and PeftModel:
            # For PeftModel, we need to tokenize the prompt first
            inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)
            inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=generation_args.get("max_new_tokens", 512),
                    do_sample=generation_args.get("do_sample", True),
                    temperature=generation_args.get("temperature", 0.4),
                    top_k=generation_args.get("top_k", 150),
                    top_p=generation_args.get("top_p", 0.75),
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )
            generated = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            return generated[len(prompt):] if generated.startswith(prompt) else generated
        else:
            # Use pipeline inference
            if not generation_args:
                generation_args = self.default_generation_args
            outputs = self.pipe(prompt, **generation_args)
            generated = outputs[0]["generated_text"]
            return generated[len(prompt):] if generated.startswith(prompt) else generated

class ChatHandler:
    def __init__(self, base_model_path, device, adapter_path=None):
        self.tokenizer = AutoTokenizer.from_pretrained(base_model_path)
        if adapter_path and PeftModel:
            model = AutoModelForCausalLM.from_pretrained(
                base_model_path,
                torch_dtype=torch.bfloat16,
                device_map=device,
                trust_remote_code=True
            )
            model = PeftModel.from_pretrained(
                model,
                adapter_path,
                torch_dtype=torch.bfloat16,
                device_map=device
            )
            self.model = model
        else:
            self.model = AutoModelForCausalLM.from_pretrained(
                base_model_path,
                torch_dtype=torch.bfloat16,
                device_map=device,
            )
        self.device = device
        self.adapter_path = adapter_path
        self.base_model_path = base_model_path
        
    @property
    def default_generation_args(self):
        return {
            "max_new_tokens": 512, 
        }

    def infer(self, prompt, **generation_args):
        if not generation_args:
            generation_args = self.default_generation_args
        eos_token_id = self.tokenizer.eos_token_id
        generation_args.setdefault("pad_token_id", eos_token_id)
        generation_args.setdefault("eos_token_id", eos_token_id)
        if isinstance(prompt, str):
            prompt = [{"role": "user", "content": prompt}]
        inputs = self.tokenizer.apply_chat_template(
            prompt,
            return_tensors="pt",
            return_dict=True,
            add_generation_prompt=True
        )
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        outputs = self.model.generate(
            input_ids=inputs["input_ids"],
            attention_mask=inputs.get("attention_mask"),
            **generation_args
        )
        result = self.tokenizer.decode(
            outputs[0, inputs["input_ids"].shape[1]:],
            skip_special_tokens=True
        )
        return result

class VisionHandler:
    def __init__(self, base_model_path, device):
        self.processor = AutoProcessor.from_pretrained(base_model_path)
        self.model = AutoModelForVision2Seq.from_pretrained(base_model_path).to(device)
        self.device = device

    @property
    def default_generation_args(self):
        return {
            "max_new_tokens": 100,
        }

    def infer(self, prompt, **generation_args):
        # prompt is the conversation format (list of dicts)
        inputs = self.processor.apply_chat_template(
            prompt,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt"
        ).to(self.device)
        output = self.model.generate(**inputs, **generation_args)
        return self.processor.decode(output[0], skip_special_tokens=True)

def needs_chat_handler(base_model_path):
    return "instruct" in base_model_path.lower() or "chat" in base_model_path.lower()

def is_vision_handler(base_model_path):
    return "vision" in base_model_path.lower()

def main():
    # RabbitMQ details
    rabbitmq_host = "128.16.12.219"
    rabbitmq_port = 5672
    rabbitmq_user = "guest"
    rabbitmq_pass = "guest"
    input_queue = "engineered_prompt"
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

    handler_cache = {}

    def get_handler(base_model_path, device, adapter_path=None):
        key = (base_model_path, adapter_path, device)
        if key not in handler_cache:
            print(f"Loading model: {base_model_path}, adapter: {adapter_path} on {device}")
            if is_vision_handler(base_model_path):
                handler_cache[key] = VisionHandler(base_model_path, device)
            elif needs_chat_handler(base_model_path):
                handler_cache[key] = ChatHandler(base_model_path, device, adapter_path)
            else:
                handler_cache[key] = PipelineHandler(base_model_path, device, adapter_path)
        return handler_cache[key]

    def on_message(ch, method, properties, body):
        try:
            message = json.loads(body)
            input_list = message["input"]
            base_model_path = message["base_model_path"]
            adapter_path = message.get("adapter_path")
            device = "hpu"

            if not base_model_path or not isinstance(base_model_path, str):
                print("Error: base_model_path is None or invalid in message:", message)
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            
            handler = get_handler(base_model_path, device, adapter_path)

            if is_vision_handler(base_model_path):
                try:
                    parsed_prompt = parse_input(message, is_vision_model=True)
                except ValueError as ve:
                    response = {
                        "conversation_id": message.get("conversation_id"),
                        "result": str(ve),
                    }
                    ch.basic_publish(
                        exchange="",
                        routing_key=output_queue,
                        body=json.dumps(response),
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    return 
            else:
                parsed_prompt = parse_input(message, is_vision_model=False)
            
            print("Prompt sent to model:", parsed_prompt) 
            
            # Use handler's defaults unless message overrides
            generation_args = message.get("generation_args", handler.default_generation_args)
            print(f"Received prompt for model: {base_model_path}")
            result = handler.infer(parsed_prompt, **generation_args)
            result = extract_llama3_answer(result)
            print(f"Result: {result!r}")

            response = {
                "conversation_id": message.get("conversation_id"),
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
