import json

# Function to convert rows to instruction-tuning format for habana
def convert_row(row):
    return {
        "text": "### Instruction:\nGenerate source code of class member functions in Java based on given natural language description and class environment.\n### Input:\n" + 
                row["nl"].strip() + "\n### Response:" + row["code"].strip() 
    }

# Convert a JSONL file to instruction-tuning JSON format
def convert_jsonl_to_instruction_format(input_jsonl, output_json):
    with open(input_jsonl, "r", encoding="utf-8") as f:
        data = [json.loads(line) for line in f if line.strip()]

    converted = [convert_row(row) for row in data]

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(converted, f, indent=2, ensure_ascii=False)

    print(f"Done: Converted {input_jsonl} -> {output_json}")

# Process the three splits
convert_jsonl_to_instruction_format("train.json", "concode_train.json")
convert_jsonl_to_instruction_format("dev.json", "concode_val.json")
convert_jsonl_to_instruction_format("test.json", "concode_test.json")
