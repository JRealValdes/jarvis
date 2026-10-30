"""Public reads of images Jarvis stored for chat replies."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from jarvis.infrastructure.images.store import open_stored_image

router = APIRouter(tags=["images"])


@router.get("/images/{image_id}")
def get_stored_image(image_id: str) -> FileResponse:
    """
    Return one stored image.

    No JWT: markdown image tags cannot send a bearer token. The id is an
    unguessable content hash. Expired files are deleted and answer 404.

    Args:
        image_id: Hex id from the chat markdown URL.

    Returns:
        The image bytes.

    Raises:
        HTTPException: 404 when the id is unknown or the file has expired.
    """
    opened = open_stored_image(image_id)
    if opened is None:
        raise HTTPException(status_code=404, detail="Image not found.")
    path, media_type = opened
    return FileResponse(
        path,
        media_type=media_type,
        filename=path.name,
        content_disposition_type="inline",
    )
