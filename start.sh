#!/bin/bash
# start.sh

# Start uvicorn in the background
uvicorn download_model:app --host 0.0.0.0 --port 8001 &

# Start inference script 
# python inference/generic_inference.py

wait
