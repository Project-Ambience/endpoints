from fastapi import FastAPI, Request
from huggingface_hub import snapshot_download
import requests
import threading
import os

HF_CACHE = "/models"

app = FastAPI()

def install_model_and_notify(model_path, callback_url, install_id):
    try:
        snapshot_download(repo_id=model_path, cache_dir=HF_CACHE, resume_download=True, local_files_only=False) 
        status = "success" 
    except Exception as e:
        status = "fail"
        print(f"Error during install: {e}")

    payload = {
        "id": install_id,
        "status": status
    }

    try:
        requests.post(callback_url, json=payload)
    except Exception as e:
        print("Failed to notify web backend:", e)

@app.post("/models/install")
async def install_model(request: Request):
    data = await request.json()
    model_path = data["model_path"]
    callback_url = data["callback_url"]
    install_id = data.get("id")

    # Run model install in a new thread so API responds instantly
    thread = threading.Thread(target=install_model_and_notify, args=(model_path, callback_url, install_id))
    thread.start()

    return {"status": "started", "message": f"Started installing {model_path}"}
