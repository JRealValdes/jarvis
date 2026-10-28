"""User-attached images for multimodal chat turns."""

from jarvis.infrastructure.images.attachments import (
    HISTORY_IMAGE_MARKER,
    IMAGE_ONLY_PROMPT,
    MAX_IMAGE_BYTES,
    MAX_IMAGES_PER_TURN,
    OMITTED_IMAGE_NOTE,
    SUPPORTED_IMAGE_MEDIA_TYPES,
    ImageAttachmentError,
    VisionNotSupportedError,
    build_human_message,
    human_content_for_history,
    images_from_file_paths,
    normalize_image_attachments,
    prepare_messages_for_model,
)

__all__ = [
    "HISTORY_IMAGE_MARKER",
    "IMAGE_ONLY_PROMPT",
    "MAX_IMAGE_BYTES",
    "MAX_IMAGES_PER_TURN",
    "OMITTED_IMAGE_NOTE",
    "SUPPORTED_IMAGE_MEDIA_TYPES",
    "ImageAttachmentError",
    "VisionNotSupportedError",
    "build_human_message",
    "human_content_for_history",
    "images_from_file_paths",
    "normalize_image_attachments",
    "prepare_messages_for_model",
]
