"""A request sent through the public contact form of the landing page."""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

ContactInterest = Literal["agents", "channels", "voice", "automation", "knowledge", "plans", "other"]


class ContactRequest(BaseModel):
    """What a prospect tells us from the landing page.

    Attributes:
        name (str): Who is writing.
        email (str): Where to answer.
        company (Optional[str]): Their business, if given.
        phone (Optional[str]): A phone number, if given.
        interest (ContactInterest): What they are interested in.
        message (str): What they need.
    """

    name: str = Field(min_length=2, max_length=120)
    email: str = Field(max_length=254)
    company: Optional[str] = Field(default=None, max_length=160)
    phone: Optional[str] = Field(default=None, max_length=40)
    interest: ContactInterest = "other"
    message: str = Field(min_length=10, max_length=4000)

    @field_validator("name", "company", "phone", "message", mode="before")
    @classmethod
    def _strip(cls, value: Optional[str]) -> Optional[str]:
        """Trim whitespace; an empty optional field becomes None.

        Args:
            value (Optional[str]): The raw value.

        Returns:
            Optional[str]: The trimmed value, or None if it was blank.
        """
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        """Check the address looks like one (same rule as user accounts).

        Args:
            value (str): The trimmed address.

        Returns:
            str: The address, lowercased.

        Raises:
            ValueError: If it is not an email address.
        """
        value = value.strip().lower()
        if not _EMAIL_RE.match(value):
            raise ValueError("invalid email")
        return value
