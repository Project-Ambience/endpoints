#!/usr/bin/env python3
import os
# Use LAZY plugin consistently
os.environ["PT_HPU_LAZY_MODE"]                 = "1"
os.environ["PT_HPU_ENABLE_REFINE_DYNAMIC_SHAPES"] = "1"
os.environ["PT_HPU_LOG_LEVEL"] = "warning"
os.environ["HABANA_LOG_LEVEL"] = "WARN"

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
from optimum.habana.utils import set_seed

def load_model_and_tokenizer(base_model_path, lora_checkpoint_path, device="hpu"):
    print(f"Loading base model from: {base_model_path}")
    tokenizer = AutoTokenizer.from_pretrained(base_model_path)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        torch_dtype=torch.bfloat16,
        device_map="auto" if device == "hpu" else None,
        trust_remote_code=True
    )

    print(f"Loading LoRA adapters from: {lora_checkpoint_path}")
    model = PeftModel.from_pretrained(
        model,
        lora_checkpoint_path,
        torch_dtype=torch.bfloat16,
        device_map="auto" if device == "hpu" else None,
    )

    # No explicit model.to("hpu") — device_map has already placed it on HPU
    return model, tokenizer

def format_prompt(instruction, input_text=""):
    if input_text:
        return f"### Instruction:\n{instruction}\n### Input:\n{input_text}\n### Response:\n"
    return f"### Instruction:\n{instruction}\n### Response:\n"

def generate_response(model, tokenizer, prompt, max_length=2048, temperature=0.7, top_p=0.9):
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)
    inputs = {k: v.to("hpu") for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_length=max_length,
            temperature=temperature,
            top_p=top_p,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
            repetition_penalty=1.1,
            no_repeat_ngram_size=3,
        )

    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    if "### Response:" in response:
        response = response.split("### Response:")[-1].strip()
    return response

def main():
    base_model      = "m42-health/Llama3-Med42-8B"
    lora_checkpoint = "/models/llama3-med42-8b_42"
    device          = "hpu"
    max_length      = 2048
    temperature     = 0.7
    top_p           = 0.9

    set_seed(42)
    print("Loading model and tokenizer...")
    model, tokenizer = load_model_and_tokenizer(base_model, lora_checkpoint, device)

    print("\n=== Running Inference on Medical Dialogue ===")
    instruction = "Summarize the following doctor-patient dialogue into a clinical note."
    input_text = """Doctor: Hello, what brings you in today?
Patient: I've been having severe chest pain for the past 2 days..."""
    prompt = format_prompt(instruction, input_text)

    print(f"Input Prompt:\n{'-'*50}\n{prompt}\n{'-'*50}\nGenerating clinical note...")
    response = generate_response(model, tokenizer, prompt, max_length, temperature, top_p)
    print(f"\nGenerated Clinical Note:\n{'-'*50}\n{response}\n{'-'*50}")

if __name__ == "__main__":
    main()
