import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import FastAPI, Request, Form
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from agents.session import ask_jarvis, reset_cache
from enums.core_enums import ModelEnum
from config import DEFAULT_MODEL
import uvicorn

app = FastAPI()

class AskInput(BaseModel):
    message: str
    model_name: str = DEFAULT_MODEL.name
    thread_id: str

@app.post("/ask")
async def ask_json(input_data: AskInput):
    model_enum = ModelEnum[input_data.model_name]
    answer = ask_jarvis(input_data.message, model_enum, input_data.thread_id)
    return {"response": answer}

@app.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    Body: str = Form(...),
    From: str = Form(...),
    ProfileName: str = Form(None)
):
    model_enum = DEFAULT_MODEL
    thread_id = From     # Use the phone number as thread_id to maintain continuity between messages from the same user
    responses = ask_jarvis(Body, model_enum, thread_id)
    response_text = "\n".join(responses)
    return PlainTextResponse(response_text)

@app.post("/reset")
async def reset_memory():
    reset_cache()
    return {"status": "ok", "message": "Memory reset"}

if __name__ == "__main__":
    uvicorn.run("api.main_api:app", host="0.0.0.0", port=8000, reload=True)
