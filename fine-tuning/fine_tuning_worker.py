#!/usr/bin/env python3
"""
The script fine-tunes the m42-health/Llama3-Med42-8B model using LLaMA Factory framework.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any

# Add LLaMA Factory to path
LLAMA_FACTORY_PATH = "/app/LLaMA-Factory/src"
if os.path.exists(LLAMA_FACTORY_PATH):
    sys.path.append(LLAMA_FACTORY_PATH)

try:
    # from llamafactory.train.tuner import run_exp
    from llamafactory.train.sft import run_sft
    from llamafactory.hparams import get_train_args
except ImportError:
    print("LLaMA Factory not found. Please ensure it's installed in /app/LLaMA-Factory")
    sys.exit(1)


class Med42FineTuner:
    """Fine-tuning class for Med42 model using LLaMA Factory"""

    def __init__(self,
                 base_model: str = "m42-health/Llama3-Med42-8B",
                 data_dir: str = "./data/medical_finetune_test_data",
                 output_dir: str = "./outputs/med42_finetuned"):
        self.base_model = base_model
        self.data_dir = data_dir
        self.output_dir = output_dir

        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

    def create_sample_data(self) -> str:
        """Dummy data for testing the fine-tuning script"""
        sample_data = [
            {
                "instruction": "What are the symptoms of diabetes?",
                "input": "",
                "output": "Common symptoms of diabetes include increased thirst, frequent urination, extreme hunger, unexplained weight loss, fatigue, irritability, blurred vision, slow-healing sores, and frequent infections. Type 1 diabetes symptoms can develop quickly, while Type 2 diabetes symptoms may develop slowly over time."
            },
            {
                "instruction": "How is hypertension diagnosed?",
                "input": "",
                "output": "Hypertension (high blood pressure) is diagnosed through blood pressure measurements. A reading of 130/80 mmHg or higher on multiple occasions typically indicates hypertension. Diagnosis may involve multiple visits, 24-hour ambulatory monitoring, or home blood pressure monitoring. Additional tests may include blood tests, urine tests, and imaging studies to assess organ damage."
            },
            {
                "instruction": "What are the treatment options for asthma?",
                "input": "",
                "output": "Asthma treatment includes both long-term control medications and quick-relief medications. Long-term controllers include inhaled corticosteroids, long-acting beta agonists, leukotriene modifiers, and theophylline. Quick-relief medications include short-acting beta agonists and anticholinergics. Treatment plans are personalized based on asthma severity and individual response to medications."
            },
            {
                "instruction": "Explain the difference between Type 1 and Type 2 diabetes",
                "input": "",
                "output": "Type 1 diabetes is an autoimmune condition where the body's immune system attacks insulin-producing cells in the pancreas, leading to little or no insulin production. It typically develops in childhood or young adulthood and requires lifelong insulin therapy. Type 2 diabetes occurs when the body becomes resistant to insulin or doesn't produce enough insulin. It's often associated with lifestyle factors and can sometimes be managed with diet, exercise, and oral medications."
            },
            {
                "instruction": "What are the risk factors for heart disease?",
                "input": "",
                "output": "Major risk factors for heart disease include high blood pressure, high cholesterol, smoking, diabetes, obesity, physical inactivity, poor diet, excessive alcohol consumption, age (risk increases with age), family history, and stress. Some risk factors like age and family history cannot be changed, while others like smoking, diet, and exercise can be modified to reduce risk."
            }
        ]
        data_file = os.path.join(self.data_dir, "medical_finetune_test_data.json")
        with open(data_file, "w") as f:
            json.dump(sample_data, f, indent=2)
        print(f"Sample data created at: {data_file}")
        return data_file


if __name__ == "__main__":
    tuner = Med42FineTuner()
    data_file = tuner.create_sample_data()

    sys.argv = [sys.argv[0], "med42_config.yaml"]

    
    # convert to argparse namespace and override defaults
    # args = get_train_args()
    model_args, data_args, training_args, finetuning_args, generating_args = get_train_args()
    run_sft(
        model_args,
        data_args,
        training_args,
        finetuning_args,
        generating_args,
        callbacks=None,       # (optional)
    )
    # launch fine-tuning
    # run_exp(args)
