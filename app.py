import gradio as gr
from agents.assistant import ask_jarvis, reset_agents_cache
from enums.core_enums import ModelEnums
from tools.speech_to_text import speech_to_text_tool

model_options = list(ModelEnums.__members__.keys())
default_model = "GPT_3_5"

def respond(message, chat_history, model_name):
    response = ask_jarvis(message, model_name)
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

def reset_cache():
    reset_agents_cache()
    return "Agents cache resetted."

with gr.Blocks() as demo:
    chatbot = gr.Chatbot(height=500, type='messages')
    model_dropdown = gr.Dropdown(choices=model_options, value=default_model, label="Select the model")

    with gr.Row():
        message = gr.Textbox(placeholder="Write your message to Jarvis here...")
        send_btn = gr.Button("Send")

    with gr.Row():
        audio_input = gr.Audio(label="Speak to Jarvis", type="filepath", format="wav")
        voice_btn = gr.Button("Send Voice")

    reset_btn = gr.Button("Reset memory")
    status = gr.Textbox(label="Status", interactive=False)

    # Text input
    send_btn.click(fn=respond, inputs=[message, chatbot, model_dropdown], outputs=[chatbot, message])
    message.submit(fn=respond, inputs=[message, chatbot, model_dropdown], outputs=[chatbot, message])

    # Audio input
    voice_btn.click(fn=respond_audio, inputs=[audio_input, chatbot, model_dropdown], outputs=[chatbot, status])

    # Reset cache
    reset_btn.click(fn=reset_cache, inputs=None, outputs=status)

if __name__ == "__main__":
    demo.launch()
