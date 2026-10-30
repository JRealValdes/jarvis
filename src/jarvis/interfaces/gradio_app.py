"""Gradio interface for Jarvis chat (text, images, and voice)."""

from urllib.parse import urlparse

import gradio as gr

from jarvis.agents.session import ask_jarvis, reset_cache
from jarvis.core.config import API_PORT, DEFAULT_MODEL, LOCAL_THREAD_ID
from jarvis.infrastructure.images.store import (
    absolutize_stored_image_urls,
    origin_for_api,
)
from jarvis.core.enums import ModelEnum
from jarvis.infrastructure.images import (
    IMAGE_ONLY_PROMPT,
    ImageAttachmentError,
    VisionNotSupportedError,
    images_from_file_paths,
)
from jarvis.tools.builtins.speech_to_text import speech_to_text_tool

model_options = list(ModelEnum.__members__.keys())
model_used = DEFAULT_MODEL
thread_id = LOCAL_THREAD_ID


def browser_image_origin(request: gr.Request | None) -> str:
    """
    API origin for images shown in this Gradio page.

    Uses the host of the page the browser opened, and the API port. A page
    opened on the LAN stays on the LAN. A page opened through Tailscale stays
    on Tailscale. No fixed public base URL.

    Args:
        request: Gradio request for this click, if the runtime provided one.

    Returns:
        Origin with no path.
    """
    raw = getattr(request, "url", None) if request is not None else None
    if isinstance(raw, str):
        parsed = urlparse(raw)
        return origin_for_api(parsed.scheme, parsed.hostname, API_PORT)
    return origin_for_api(
        getattr(raw, "scheme", None),
        getattr(raw, "hostname", None),
        API_PORT,
    )


def _file_paths(image_files: list[str] | str | None) -> list[str]:
    """Normalize Gradio's file widget value to a list of paths."""
    if not image_files:
        return []
    if isinstance(image_files, str):
        return [image_files]
    return [path for path in image_files if path]


def _user_bubble(text: str, paths: list[str]) -> str | list:
    """Build a Gradio user message that shows text and attached images."""
    if not paths:
        return text
    blocks: list = [text or IMAGE_ONLY_PROMPT]
    blocks.extend({"path": path} for path in paths)
    return blocks


async def respond(
    message: str,
    image_files: list[str] | str | None,
    chat_history: list,
    model_used: ModelEnum | str,
    request: gr.Request,
) -> tuple[list, str, list[str] | str | None]:
    """
    Send a text message, with optional images, and update the Gradio history.

    Args:
        message: User text.
        image_files: Uploaded image paths from the file widget.
        chat_history: Previous history (Gradio messages format).
        model_used: ModelEnum or enum member name as str.
        request: Gradio request. Its host selects the image URL.

    Returns:
        Tuple of (updated chat_history, cleared textbox, cleared file widget).
    """
    if isinstance(model_used, str):
        model_used = ModelEnum[model_used]

    chat_history = chat_history or []
    paths = _file_paths(image_files)
    text = (message or "").strip()
    if not text and not paths:
        return chat_history, "", None

    try:
        images = images_from_file_paths(paths)
        response = await ask_jarvis(
            text,
            model_used,
            thread_id=thread_id,
            images=images or None,
        )
    except (ImageAttachmentError, VisionNotSupportedError) as exc:
        chat_history.append({"role": "assistant", "content": exc.message})
        return chat_history, message or "", image_files

    chat_history.append({"role": "user", "content": _user_bubble(text, paths)})

    image_origin = browser_image_origin(request)
    for response_msg in response:
        if isinstance(response_msg, str):
            response_msg = absolutize_stored_image_urls(response_msg, image_origin)
        chat_history.append({"role": "assistant", "content": response_msg})

    return chat_history, "", None


async def respond_audio(
    audio_file: str | None,
    chat_history: list,
    model_name: ModelEnum | str,
    request: gr.Request,
) -> tuple[list, str]:
    """
    Transcribe audio and delegate to ``respond``.

    Args:
        audio_file: Path to the audio file or None.
        chat_history: Gradio history.
        model_name: Selected model.
        request: Gradio request, forwarded so image URLs use this page's host.

    Returns:
        Tuple of (history, status or error message).
    """
    if audio_file is None:
        return chat_history, "No audio file was provided."

    try:
        text = speech_to_text_tool.invoke({"file_path": audio_file})
    except Exception as e:
        return chat_history, f"Error transcribing audio: {e}"

    history, _cleared, _files = await respond(
        text, None, chat_history, model_name, request
    )
    return history, ""


async def reset_chat() -> tuple[str, list]:
    """
    Reset the global session cache, close MCP, and clear the chat.

    Returns:
        Tuple of (status message, empty history list).
    """
    await reset_cache()
    return "Chat memory reset.", []


demo = gr.Blocks()
with demo:
    chatbot = gr.Chatbot(height=500, render_markdown=True)

    with gr.Row():
        message = gr.Textbox(
            placeholder="Type your message for Jarvis...",
            label="Your message",
        )
        image_input = gr.File(
            label="Attach images",
            file_count="multiple",
            file_types=["image"],
            type="filepath",
        )
        send_btn = gr.Button("Send")

    with gr.Row():
        audio_input = gr.Audio(label="Speak to Jarvis", type="filepath", format="wav")
        voice_btn = gr.Button("Send voice")

    model_dropdown = gr.Dropdown(
        choices=model_options,
        value=model_used.name,
        label="Model",
    )

    reset_btn = gr.Button("Reset memory")
    status = gr.Textbox(label="Status", interactive=False)

    send_btn.click(
        fn=respond,
        inputs=[message, image_input, chatbot, model_dropdown],
        outputs=[chatbot, message, image_input],
    )
    message.submit(
        fn=respond,
        inputs=[message, image_input, chatbot, model_dropdown],
        outputs=[chatbot, message, image_input],
    )
    voice_btn.click(fn=respond_audio, inputs=[audio_input, chatbot, model_dropdown], outputs=[chatbot, status])
    reset_btn.click(fn=reset_chat, inputs=None, outputs=[status, chatbot])
