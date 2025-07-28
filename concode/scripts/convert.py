import json

def convert_concode_line(line):
    """
    Convert a single line from Concode format to new format.
    """
    entry = json.loads(line)
    nl = entry.get("nl", "")
    code = entry.get("code", "")

    # Split the NL string into description and class environment
    if "|" in nl:
        description, class_env = map(str.strip, nl.split("|", 1))
    else:
        description = nl.strip()
        class_env = ""

    new_entry = {
        "instruction": "Generate source code of class member functions in Java based on given natural language description and class environment.",
        "input": f"Description: {description}\nClass Environment:\n{class_env}",
        "output": code
    }
    return new_entry

def convert_concode_file(input_path, output_path, limit=None):
    """
    Convert a Concode-format JSONL file to the new JSONL format.
    """
    with open(input_path, "r") as infile, open(output_path, "w") as outfile:
        for i, line in enumerate(infile):
            if limit and i >= limit:
                break
            try:
                new_entry = convert_concode_line(line)
                outfile.write(json.dumps(new_entry, ensure_ascii=False) + "\n")
            except Exception as e:
                print(f"Skipping line {i} due to error: {e}")

if __name__ == "__main__":
    # Example usage
    input_file = "train.json"       
    output_file = "train_converted.jsonl"
    convert_concode_file(input_file, output_file, limit=100)

