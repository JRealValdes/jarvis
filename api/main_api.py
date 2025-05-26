from fastapi import FastAPI, Request, Form
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from agents.assistant import ask_jarvis, reset_agents_cache
import uvicorn

app = FastAPI()

# ---------- MODELO PARA USO JSON ----------
class AskInput(BaseModel):
    message: str
    model_name: str = "GPT_3_5"

# ---------- ENDPOINT API REST JSON ----------
@app.post("/ask")
async def ask_json(input_data: AskInput):
    answer = ask_jarvis(input_data.message, input_data.model_name)
    return {"response": answer}

# ---------- ENDPOINT PARA TWILIO WHATSAPP ----------
@app.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    Body: str = Form(...),
    From: str = Form(...),
    ProfileName: str = Form(None)
):
    response_text = ask_jarvis(Body, "GPT_3_5")
    return PlainTextResponse(response_text)

# ---------- RESET AGENTES EN AMBOS CASOS ----------
@app.post("/reset")
async def reset_memory():
    reset_agents_cache()
    return {"status": "ok", "message": "Memory reset"}

# ---------- EJECUCIÓN LOCAL ----------
if __name__ == "__main__":
    uvicorn.run("api.main_api:app", host="0.0.0.0", port=8000, reload=True)
