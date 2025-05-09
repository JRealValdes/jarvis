from agents.assistant import ask_jarvis

while True:
    query = input("Hola, señor. ¿Con qué puedo ayudarle hoy? ")
    if query.lower() in ["salir", "exit", "quit"]:
        break
    response = ask_jarvis(query)
    print("Jarvis:", response)
