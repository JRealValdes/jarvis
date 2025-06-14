import gradio as gr
from agents.session import ask_jarvis, reset_cache
from enums.core_enums import ModelEnum
from config import DEFAULT_MODEL
from tools.speech_to_text import speech_to_text_tool

model_options = list(ModelEnum.__members__.keys())
model_used = DEFAULT_MODEL
thread_id = "1" # Parameterize this in the future

def respond(message, chat_history, model_used):
    if isinstance(model_used, str):
        model_used = ModelEnum[model_used]  # Convertir de str a enum
    
    response = ask_jarvis(message, model_used, thread_id=thread_id)
    chat_history = chat_history or []
    chat_history.append({"role": "user", "content": message})
    chat_history.append({"role": "assistant", "content": response})
    return chat_history, ""


def respond_audio(audio_file, chat_history, model_name):
    if audio_file is None:
        return chat_history, "No audio file provided."

    try:
        # Transcribe the audio
        text = speech_to_text_tool.invoke(audio_file)
    except Exception as e:
        return chat_history, f"Error transcribing audio: {str(e)}"
    
    # Use transcribed text to get Jarvis response
    return respond(text, chat_history, model_name)

def reset_chat():
    reset_cache()
    return "Chat cache resetted.", []

with gr.Blocks() as demo:
    chatbot = gr.Chatbot(height=500, type='messages')

    with gr.Row():
        message = gr.Textbox(placeholder="Write your message to Jarvis here...")
        send_btn = gr.Button("Send")

    with gr.Row():
        audio_input = gr.Audio(label="Speak to Jarvis", type="filepath", format="wav")
        voice_btn = gr.Button("Send Voice")

    model_dropdown = gr.Dropdown(choices=model_options, value=model_used.name, label="Select the model")

    reset_btn = gr.Button("Reset memory")
    status = gr.Textbox(label="Status", interactive=False)

    send_btn.click(fn=respond, inputs=[message, chatbot, model_dropdown], outputs=[chatbot, message])
    message.submit(fn=respond, inputs=[message, chatbot, model_dropdown], outputs=[chatbot, message])

    voice_btn.click(fn=respond_audio, inputs=[audio_input, chatbot, model_dropdown], outputs=[chatbot, status])
    reset_btn.click(
        fn=reset_chat,
        inputs=None,
        outputs=[status, chatbot]
    )


if __name__ == "__main__":
    demo.launch()
