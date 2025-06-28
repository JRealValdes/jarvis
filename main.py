from config import DEFAULT_MODEL
from agents.session import ask_jarvis

model_used = DEFAULT_MODEL
thread_id = "1" # Parameterize this in the future

while True:
    question = input("Usuario: ")
    if question.lower() in ["salir", "exit", "quit"] or ("eso es todo" in question.lower() and "jarvis" in question.lower()):
        break
    response = ask_jarvis(question, model_used, thread_id=thread_id)
    for response_msg in response:
        print("Jarvis:", response_msg)
