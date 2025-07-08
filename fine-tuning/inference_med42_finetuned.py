#!/usr/bin/env python3
"""
LoRA Fine-tuned Model Inference Script for Intel Gaudi
Loads Med42 base model with LoRA adapters and runs inference
"""

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
from optimum.habana.utils import set_seed
import os

def load_model_and_tokenizer(base_model_path, lora_checkpoint_path, device="hpu"):
    """Load base model with LoRA adapters"""
    
    print(f"Loading base model from: {base_model_path}")
    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(base_model_path)
    
    # Add pad token if missing
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # Load base model
    model = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        torch_dtype=torch.bfloat16,
        device_map="auto" if device == "hpu" else None,
        trust_remote_code=True
    )
    
    print(f"Loading LoRA adapters from: {lora_checkpoint_path}")
    # Load LoRA adapters
    model = PeftModel.from_pretrained(
        model,
        lora_checkpoint_path,
        torch_dtype=torch.bfloat16,
        device_map="auto" if device == "hpu" else None,
    )
    
    # Move to HPU if specified
    if device == "hpu":
        model = model.to("hpu")
    
    return model, tokenizer

def format_prompt(instruction, input_text=""):
    """Format prompt in the training format"""
    if input_text:
        return f"### Instruction:\n{instruction}\n### Input:\n{input_text}\n### Response:\n"
    else:
        return f"### Instruction:\n{instruction}\n### Response:\n"

def generate_response(model, tokenizer, prompt, max_length=2048, temperature=0.7, top_p=0.9):
    """Generate response using the model"""
    
    # Tokenize input
    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=2048
    )
    
    # Move to HPU
    inputs = {k: v.to("hpu") for k, v in inputs.items()}
    
    # Generate
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
    
    # Decode response
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    # Extract only the generated part (after "### Response:")
    if "### Response:" in response:
        response = response.split("### Response:")[-1].strip()
    
    return response

def main():
    # Configuration
    base_model = "m42-health/Llama3-Med42-8B"
    lora_checkpoint = "/app/endpoints/fine-tuning/finetune_runs/med42_finetuned_full/checkpoint-3"
    device = "hpu"
    max_length = 2048
    temperature = 0.7
    top_p = 0.9
    
    # Set environment variables for HPU
    os.environ["PT_HPU_LAZY_MODE"] = "1"
    os.environ["PT_HPU_ENABLE_REFINE_DYNAMIC_SHAPES"] = "1"
    
    # Set seed for reproducibility
    set_seed(42)
    
    # Load model and tokenizer
    print("Loading model and tokenizer...")
    model, tokenizer = load_model_and_tokenizer(
        base_model,
        lora_checkpoint,
        device
    )
    
    # Static example - medical dialogue
    print("\n=== Running Inference on Medical Dialogue ===")
    
    instruction = "Summarize the following doctor-patient dialogue into a clinical note."
    input_text = """Doctor: Hello, what brings you in today?
Patient: I've been having severe chest pain for the past 2 days. It's really worrying me.
Doctor: I'm sorry to hear that. Can you describe the pain for me?
Patient: It's a sharp, stabbing pain in the center of my chest. It gets worse when I breathe deeply or cough.
Doctor: Any other symptoms? Shortness of breath, nausea, sweating?
Patient: Yes, I've been short of breath and I feel a bit nauseous. No sweating though.
Doctor: When did this start exactly?
Patient: Two days ago, around 3 PM. I was just sitting at my desk at work.
Doctor: Any history of heart problems or recent travel?
Patient: No heart problems, but I did take a long flight from Europe last week.
Doctor: Given your symptoms and recent travel, I'm concerned about a possible pulmonary embolism. We need to do some tests immediately including a CT scan and blood work."""
    
    prompt = format_prompt(instruction, input_text)
    
    print(f"Input Prompt:\n{'-'*50}")
    print(prompt)
    print(f"{'-'*50}")
    print("Generating clinical note...")
    
    response = generate_response(
        model, tokenizer, prompt,
        max_length=max_length,
        temperature=temperature,
        top_p=top_p
    )
    
    print(f"\nGenerated Clinical Note:\n{'-'*50}")
    print(response)
    print(f"{'-'*50}")

if __name__ == "__main__":
    main()