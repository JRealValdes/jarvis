from enums.core_enums import ModelEnum
from agents.assistant import ask_jarvis

model_used = ModelEnum.GPT_3_5

while True:
    query = input("Hola, señor. ¿Con qué puedo ayudarle hoy? ")
    if query.lower() in ["salir", "exit", "quit"] or ("eso es todo" in query.lower() and "jarvis" in query.lower()):
        break
    response = ask_jarvis(query, model_used.name)
    print("Jarvis:", response)
