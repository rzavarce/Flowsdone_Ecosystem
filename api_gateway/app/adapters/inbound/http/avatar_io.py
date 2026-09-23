"""HTTP plumbing shared by the endpoints that upload and serve profile photos
(`/me/avatar` and `/internal/admin/users/{id}/avatar`).

Uploads are the raw image bytes as the request body (`Content-Type:
image/jpeg|png|webp`), not multipart: one field, no extra dependency. The
real type is sniffed from the bytes by `SetAvatarUseCase`.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, Response

from app.application.use_cases.manage_profile import AVATAR_MAX_BYTES
from app.domain.models.user import UserAvatar


async def read_image_body(request: Request) -> bytes:
    """Read an uploaded photo, refusing oversized bodies early.

    Args:
        request (Request): The upload request.

    Returns:
        bytes: The body.

    Raises:
        HTTPException: 413 if it is (or declares to be) over `AVATAR_MAX_BYTES`.
    """
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > AVATAR_MAX_BYTES:
        raise HTTPException(status_code=413, detail="image too large")
    data = await request.body()
    if len(data) > AVATAR_MAX_BYTES:
        raise HTTPException(status_code=413, detail="image too large")
    return data


def avatar_response(avatar: UserAvatar) -> Response:
    """Serve a stored photo.

    The console requests it with `?v=<avatar_updated_at>`, so a long private
    cache is safe: a new photo means a new URL.

    Args:
        avatar (UserAvatar): The photo.

    Returns:
        Response: The image, `nosniff` and privately cacheable.
    """
    return Response(
        content=avatar.data,
        media_type=avatar.content_type,
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )
