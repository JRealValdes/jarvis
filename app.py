import gradio as gr
from agents.assistant import ask_jarvis
from enums.core_enums import ModelEnums

model_options = list(ModelEnums.__members__.keys())
default_model = "GPT_3_5"

def respond(message, history, model_name):
    response = ask_jarvis(message, model_name)
    return response

demo = gr.ChatInterface(
    fn=respond,
    additional_inputs=[
        gr.Dropdown(choices=model_options, value=default_model, label="Selecciona el modelo")
    ],
    chatbot=gr.Chatbot(height=500),
    title="Jarvis",
    description="Un asistente con múltiples modelos conectados (ChatGPT, Zephyr, Mistral...)",
    theme="default"
)

if __name__ == "__main__":
    demo.launch()
