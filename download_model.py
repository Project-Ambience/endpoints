from fastapi import FastAPI, Request
from transformers import AutoModelForCausalLM, AutoTokenizer
import requests
import threading

app = FastAPI()

def install_model_and_notify(model_path, callback_url):
    try:
        AutoModelForCausalLM.from_pretrained(model_path)
        AutoTokenizer.from_pretrained(model_path)
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

    # Run model install in a new thread so API responds instantly
    thread = threading.Thread(target=install_model_and_notify, args=(model_path, callback_url))
    thread.start()

    return {"status": "started", "message": f"Started installing {model_path}"}
