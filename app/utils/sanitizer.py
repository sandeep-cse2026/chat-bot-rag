"""Input sanitization and HTML stripping utilities.

Provides:
- strip_html(): Remove HTML tags from API responses (e.g., TV Maze summaries).
- sanitize_user_input(): Clean user input before sending to the LLM.
"""
from __future__ import annotations

import re

from markupsafe import escape


def strip_html(text: str | None) -> str:
    """Remove all HTML tags from a string.

    Used primarily for TV Maze API summaries which contain raw HTML.

    Args:
        text: Raw string potentially containing HTML tags.

    Returns:
        Clean text with all HTML tags removed and whitespace normalized.

    Examples:
        >>> strip_html("<p>Hello <b>world</b></p>")
        'Hello world'
        >>> strip_html(None)
        ''
    """
    if not text:
        return ""
    # Remove HTML tags
    clean = re.sub(r"<[^>]+>", "", text)
    # Normalize whitespace (collapse multiple spaces/newlines)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()


def sanitize_user_input(text: str) -> str:
    """Sanitize user input before sending to the LLM.

    Applies the following transformations:
    1. Strip leading/trailing whitespace
    2. Escape HTML entities (XSS prevention)
    3. Truncate to max length (2000 chars)

    Args:
        text: Raw user input string.

    Returns:
        Sanitized string safe for LLM consumption.

    Raises:
        ValueError: If text is empty after stripping.
    """
    if not isinstance(text, str):
        raise ValueError("Input must be a string")

    text = text.strip()

    if not text:
        raise ValueError("Message cannot be empty")

    # Escape HTML entities
    text = str(escape(text))

    # Hard limit to prevent abuse
    max_length = 2000
    if len(text) > max_length:
        text = text[:max_length]

    return text
