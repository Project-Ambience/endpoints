from transformers import AutoModelForCausalLM, AutoTokenizer

model_name = "ibm-granite/granite-3.3-8b-instruct"
model = AutoModelForCausalLM.from_pretrained(model_name)
tokenizer = AutoTokenizer.from_pretrained(model_name)
