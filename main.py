from agents.assistant import ask_jarvis

while True:
    query = input("Hola, señor. ¿Con qué puedo ayudarle hoy? ")
    if query.lower() in ["salir", "exit", "quit"] or ("eso es todo" in query.lower() and "jarvis" in query.lower()):
        break
    response = ask_jarvis(query)
    print("Jarvis:", response)
