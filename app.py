"""Interfaz Gradio para chat con Jarvis (texto y voz)."""

import gradio as gr

from agents.session import ask_jarvis, reset_cache
from enums.core_enums import ModelEnum
from config import DEFAULT_MODEL
from tools.speech_to_text import speech_to_text_tool

model_options = list(ModelEnum.__members__.keys())
model_used = DEFAULT_MODEL
thread_id = "1"


def respond(message: str, chat_history: list, model_used: ModelEnum | str) -> tuple[list, str]:
    """
    Envía un mensaje de texto a Jarvis y actualiza el historial Gradio.

    Args:
        message: Texto del usuario.
        chat_history: Historial previo (formato messages de Gradio).
        model_used: ModelEnum o nombre de miembro del enum como str.

    Returns:
        Tupla (chat_history actualizado, cadena vacía para limpiar el textbox).
    """
    if isinstance(model_used, str):
        model_used = ModelEnum[model_used]

    response = ask_jarvis(message, model_used, thread_id=thread_id)
    chat_history = chat_history or []
    chat_history.append({"role": "user", "content": message})

    for response_msg in response:
        chat_history.append({"role": "assistant", "content": response_msg})

    return chat_history, ""


def respond_audio(
    audio_file: str | None, chat_history: list, model_name: ModelEnum | str
) -> tuple[list, str]:
    """
    Transcribe audio y delega en ``respond``.

    Args:
        audio_file: Ruta al archivo de audio o None.
        chat_history: Historial Gradio.
        model_name: Modelo seleccionado.

    Returns:
        Tupla (historial, mensaje de estado o error).
    """
    if audio_file is None:
        return chat_history, "No audio file provided."

    try:
        text = speech_to_text_tool.invoke({"file_path": audio_file})
    except Exception as e:
        return chat_history, f"Error transcribing audio: {str(e)}"

    return respond(text, chat_history, model_name)


def reset_chat() -> tuple[str, list]:
    """
    Reinicia la caché global de sesiones y vacía el chat.

    Returns:
        Tupla (mensaje de estado, lista vacía de historial).
    """
    reset_cache()
    return "Chat cache resetted.", []


with gr.Blocks() as demo:
    chatbot = gr.Chatbot(height=500, type="messages")

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
    reset_btn.click(fn=reset_chat, inputs=None, outputs=[status, chatbot])


if __name__ == "__main__":
    demo.launch()
