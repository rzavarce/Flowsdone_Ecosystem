"""Use cases for a user's optional profile data (phone, address, social
links) and profile photo - edited by the user themselves from the console
("My profile") or by an admin from Users.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse
from uuid import UUID

from app.application.dto.auth_dto import AuthenticatedUser
from app.application.use_cases._auth_common import build_authenticated_user
from app.domain.models.user import SOCIAL_NETWORKS, User
from app.domain.ports.outbound import (
    TenantRepositoryPort,
    UserAvatarRepositoryPort,
    UserRepositoryPort,
)

__all__ = [
    "AVATAR_MAX_BYTES",
    "InvalidAvatarError",
    "ProfileFields",
    "RemoveAvatarUseCase",
    "SetAvatarUseCase",
    "UpdateOwnProfileUseCase",
    "normalize_profile_fields",
    "sniff_image_type",
]

AVATAR_MAX_BYTES = 2 * 1024 * 1024
"""Upper bound for a stored photo. The PWA downsizes to 256 px JPEG (a few
tens of KB) before uploading; this only stops abuse."""

_PHONE_RE = re.compile(r"^\+?[0-9 ()./-]{4,40}$")
_MAX_ADDRESS = 300
_MAX_URL = 300


class InvalidAvatarError(ValueError):
    """The uploaded bytes are not an accepted image or are too large."""


ProfileFields = Dict[str, Any]
"""Normalized optional profile fields, ready for `UserRepositoryPort.update`:
only the keys that were sent - `phone`/`address` (an empty string means
"clear it") and `social_links` (the full replacement map)."""


def normalize_profile_fields(
    *,
    phone: Optional[str] = None,
    address: Optional[str] = None,
    social_links: Optional[Dict[str, str]] = None,
) -> ProfileFields:
    """Validate and normalize the optional profile fields.

    `None` means "not sent, leave unchanged"; an empty string (after
    trimming) clears the value. Social links with an empty URL are dropped.

    Args:
        phone (Optional[str]): Digits, spaces and `+ ( ) . / -`; 4-40 chars.
        address (Optional[str]): Free text, up to 300 chars.
        social_links (Optional[Dict[str, str]]): Network -> http(s) URL; keys
            must be in `SOCIAL_NETWORKS`.

    Returns:
        ProfileFields: The fields that were sent, normalized.

    Raises:
        ValueError: On an invalid phone, a too-long address, an unknown
            network or a URL that is not http(s).
    """
    fields: ProfileFields = {}
    if phone is not None:
        phone = phone.strip()
        if phone and not _PHONE_RE.match(phone):
            raise ValueError("phone must contain only digits, spaces and + ( ) . / -")
        fields["phone"] = phone
    if address is not None:
        address = address.strip()
        if len(address) > _MAX_ADDRESS:
            raise ValueError(f"address must be at most {_MAX_ADDRESS} characters")
        fields["address"] = address
    if social_links is not None:
        links: Dict[str, str] = {}
        for network, url in social_links.items():
            if network not in SOCIAL_NETWORKS:
                raise ValueError(f"social network must be one of: {', '.join(SOCIAL_NETWORKS)}")
            url = (url or "").strip()
            if not url:
                continue
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc or len(url) > _MAX_URL:
                raise ValueError(f"{network} must be an http(s) URL of at most {_MAX_URL} characters")
            links[network] = url
        fields["social_links"] = links
    return fields


def sniff_image_type(data: bytes) -> Optional[str]:
    """Detect the image type from its magic bytes (never trust the client's header).

    Args:
        data (bytes): Uploaded bytes.

    Returns:
        Optional[str]: `image/jpeg`, `image/png` or `image/webp`, or None
        for anything else (SVG included on purpose: it can carry scripts).
    """
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


class UpdateOwnProfileUseCase:
    """Lets the signed-in user edit their own name and optional profile data.

    Role, status, tenants and email are deliberately out of reach here:
    those only change through the admin API.
    """

    def __init__(self, *, user_repo: UserRepositoryPort, tenant_repo: TenantRepositoryPort) -> None:
        """Build the use case.

        Args:
            user_repo (UserRepositoryPort): Persists the user.
            tenant_repo (TenantRepositoryPort): Resolves tenants for the response.
        """
        self._users = user_repo
        self._tenants = tenant_repo

    async def execute(
        self,
        user_id: UUID,
        *,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        social_links: Optional[Dict[str, str]] = None,
    ) -> Optional[AuthenticatedUser]:
        """Update the caller's profile.

        Args:
            user_id (UUID): The signed-in user (from the session, never the body).
            name (Optional[str]): New display name (cannot be blank).
            phone (Optional[str]): See `normalize_profile_fields`.
            address (Optional[str]): See `normalize_profile_fields`.
            social_links (Optional[Dict[str, str]]): See `normalize_profile_fields`.

        Returns:
            Optional[AuthenticatedUser]: The updated user as the console
            sees it, or None if it no longer exists.

        Raises:
            ValueError: On a blank name or invalid profile fields.
        """
        if name is not None and not name.strip():
            raise ValueError("name is required")
        fields = normalize_profile_fields(phone=phone, address=address, social_links=social_links)
        updated = await self._users.update(
            user_id, name=name.strip() if name is not None else None, **fields
        )
        if updated is None:
            return None
        return await build_authenticated_user(updated, self._tenants)


class SetAvatarUseCase:
    """Stores a user's profile photo after checking it really is an image."""

    def __init__(self, *, avatar_repo: UserAvatarRepositoryPort) -> None:
        """Build the use case.

        Args:
            avatar_repo (UserAvatarRepositoryPort): Photo storage.
        """
        self._avatars = avatar_repo

    async def execute(self, user_id: UUID, data: bytes) -> Optional[User]:
        """Set (or replace) the photo.

        Args:
            user_id (UUID): Owner of the photo.
            data (bytes): Uploaded bytes; the type is sniffed from them.

        Returns:
            Optional[User]: The updated user, or None if it does not exist.

        Raises:
            InvalidAvatarError: Empty, over `AVATAR_MAX_BYTES`, or not a
                JPEG/PNG/WebP image.
        """
        if not data:
            raise InvalidAvatarError("the image is empty")
        if len(data) > AVATAR_MAX_BYTES:
            raise InvalidAvatarError(f"the image must be at most {AVATAR_MAX_BYTES // 1024} KB")
        content_type = sniff_image_type(data)
        if content_type is None:
            raise InvalidAvatarError("the image must be JPEG, PNG or WebP")
        return await self._avatars.put(user_id, content_type=content_type, data=data)


class RemoveAvatarUseCase:
    """Removes a user's profile photo (idempotent)."""

    def __init__(self, *, avatar_repo: UserAvatarRepositoryPort) -> None:
        """Build the use case.

        Args:
            avatar_repo (UserAvatarRepositoryPort): Photo storage.
        """
        self._avatars = avatar_repo

    async def execute(self, user_id: UUID) -> Optional[User]:
        """Remove the photo.

        Args:
            user_id (UUID): Owner of the photo.

        Returns:
            Optional[User]: The updated user, or None if it does not exist.
        """
        return await self._avatars.delete(user_id)
