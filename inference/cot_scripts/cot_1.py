from typing import List, Dict, Optional
from transformers import pipeline


### some code here to load the user input and model they selected




## if selected_model == "Med42":
      ## import med42 from ...




def few_shot_cot_template(task_instruction: str, examples: List[Dict[str, str]]) -> str:
    prompt = f"You are a helpful medical assistant specialising in {temp}. Use step-by-step reasoning.\n\n"
    for i, ex in enumerate(examples, 1):
        prompt += f"Example {i}:\n"
        prompt += f"Q: {ex['question']}\n"
        prompt += f"A: {ex['reasoning']}\n"
        prompt += f"Final Answer: {ex['answer']}\n\n"
    prompt += "Now answer the following:\n"
    prompt += f"Q: {task_instruction}\n"
    prompt += "A: Let's think step by step.\n"
    return prompt



upgraded_prompt = few_shot_cot_template()

call_to_fine_tuned_model(upgraded_prompt)
## for this above, we first need to import the model

## also the script for the fine_tuned model can return the result to the UI


## or we can do it here like this

result = call_to_fine_tuned_model(upgraded_prompt)

## and then send 'result' back to UI
