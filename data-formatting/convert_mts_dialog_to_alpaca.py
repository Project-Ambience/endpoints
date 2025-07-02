
import pandas as pd
import json

# Function to convert rows to instruction-tuning format
def convert_row(row):
    return {
        "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
        "input": row["dialogue"].strip(),
        "output": row["section_text"].strip()
    }

# Convert a CSV file to JSON format
def convert_csv_to_json(input_csv, output_json):
    df = pd.read_csv(input_csv)
    converted = [convert_row(row) for _, row in df.iterrows()]
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(converted, f, indent=2, ensure_ascii=False)
    print(f"Done: Converted {input_csv} -> {output_json}")

# Process the three splits
convert_csv_to_json("MTS-Dialog-TrainingSet.csv", "mts_dialog_train.json")
convert_csv_to_json("MTS-Dialog-ValidationSet.csv", "mts_dialog_val.json")
convert_csv_to_json("MTS-Dialog-TestSet.csv", "mts_dialog_test.json")
