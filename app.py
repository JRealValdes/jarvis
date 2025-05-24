import gradio as gr
from agents.assistant import ask_jarvis, reset_agents_cache
from enums.core_enums import ModelEnums

model_options = list(ModelEnums.__members__.keys())
default_model = "GPT_3_5"

def respond(message, chat_history, model_name):
    response = ask_jarvis(message, model_name)
    chat_history = chat_history or []
    chat_history.append((message, response))
    return chat_history, ""

def reset_cache():
    reset_agents_cache()
    return "Agents cache resetted."

with gr.Blocks() as demo:
    chatbot = gr.Chatbot(height=500)
    model_dropdown = gr.Dropdown(choices=model_options, value=default_model, label="Select the model")
    message = gr.Textbox(placeholder="Write your message to Jarvis here...")
    send_btn = gr.Button("Send")
    reset_btn = gr.Button("Reset memmory")

    status = gr.Textbox(label="Status", interactive=False)

    send_btn.click(fn=respond, inputs=[message, chatbot, model_dropdown], outputs=[chatbot, message])
    message.submit(fn=respond, inputs=[message, chatbot, model_dropdown], outputs=[chatbot, message])

    reset_btn.click(fn=reset_cache, inputs=None, outputs=status)

if __name__ == "__main__":
    demo.launch()
