import gradio as gr
from agents.assistant import ask_jarvis

def respond(message, history):
    response = ask_jarvis(message)
    return response

demo = gr.ChatInterface(
    fn=respond,
    chatbot=gr.Chatbot(height=500),
    title="Jarvis",
    description="Un asistente con múltiples modelos conectados (ChatGPT, Zephyr, Mistral...)",
    theme="default"
)

if __name__ == "__main__":
    demo.launch()
