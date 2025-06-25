from transformers import AutoModelForCausalLM, AutoTokenizer

model_name = "m42-health/Llama3-Med42-8B"
model = AutoModelForCausalLM.from_pretrained(model_name)
tokenizer = AutoTokenizer.from_pretrained(model_name)
