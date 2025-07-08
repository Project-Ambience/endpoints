#!/usr/bin/env python3
import os
import sys
import json
from argparse import ArgumentParser

def parse_args():
    p = ArgumentParser(description="Convert an Alpaca-style JSON/JSONL file into a JSON array of {'text':…} records.")
    p.add_argument("input_file", help="Path to input .json or .jsonl file")
    return p.parse_args()

def load_records(path):
    _, ext = os.path.splitext(path)
    records = []
    with open(path, "r", encoding="utf-8") as f:
        if ext.lower() == ".jsonl":
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        else:
            data = json.load(f)
            if isinstance(data, list):
                records = data
            else:
                raise ValueError(f"Expected top-level JSON array in {path}")
    return records

def format_example(ex):
    text = f"### Instruction:\n{ex.get('instruction','')}\n"
    if ex.get("input"):
        text += f"### Input:\n{ex['input']}\n"
    text += f"### Response:\n{ex.get('output','')}"
    return {"text": text}

def main():
    args = parse_args()
    records = load_records(args.input_file)
    formatted = [format_example(ex) for ex in records]

    base, _ = os.path.splitext(args.input_file)
    out_path = f"{base}_formatted.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(formatted, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(formatted)} formatted examples to {out_path}")

if __name__ == "__main__":
    main()
