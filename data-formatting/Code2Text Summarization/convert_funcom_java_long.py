import json
import re

# Extract TDAT (code) and COM (comment) from txt field
def extract_tdat_and_com(txt_field):
    tdat_match = re.search(r"TDAT:\s*(.*?)\s*COM:", txt_field, re.DOTALL)
    com_match = re.search(r"COM:\s*<s>(.*?)<\/s>", txt_field, re.DOTALL)

    tdat = tdat_match.group(1).strip() if tdat_match else ""
    com = com_match.group(1).strip() if com_match else ""
    return tdat, com

# Convert a JSONL file to new JSON file in instruction-tuning format for habana
def convert_jsonl_to_instruction_format(input_jsonl, output_json):
    with open(input_jsonl, "r", encoding="utf-8") as f:
        data = [json.loads(line) for line in f]

    converted = []
    for item in data:
        if "txt" in item:
            tdat, com = extract_tdat_and_com(item["txt"])
            if tdat and com:
                converted.append({
                    "text": "### Instruction:\nGiven a Java method, generate a concise comment that describes its functionality.\n### Input:\n" + 
                tdat + "\n### Response:" + com + "."
                })

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(converted, f, indent=2, ensure_ascii=False)
    
    print(f"Done: Converted {input_jsonl} -> {output_json}")

# Process the three splits
convert_jsonl_to_instruction_format("funcom_java_long_train.jsonl", "funcom_java_long_train.json")
convert_jsonl_to_instruction_format("funcom_java_long_test.jsonl", "funcom_java_long_test.json")
convert_jsonl_to_instruction_format("funcom_java_long_val.jsonl", "funcom_java_long_val.json")