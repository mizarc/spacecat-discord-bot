"""Shared utility command logic."""

import time
from typing import NamedTuple, TypedDict


class EmbedField(TypedDict):
    """A field within a universal embed."""

    name: str
    value: str
    inline: bool


class UniversalEmbed(TypedDict):
    """Container to store universal embed data."""

    title: str
    fields: list[EmbedField]
    color: int


def avatar(avatar_url: str | None) -> str:
    """Display the user's avatar.

    Args:
        avatar_url: URL of the user's avatar.

    Returns:
        A string containing the avatar URL or a message indicating no
        avatar exists.
    """
    if avatar_url:
        return f"Avatar URL: {avatar_url}"
    return "This user does not have an avatar."


def echo(message: str) -> str:
    """Repeat a message back.

    Args:
        message: The message to echo.

    Returns:
        The same message.
    """
    return message


def ping() -> str:
    """Return a ping response.

    Returns:
        A simple ping response string.
    """
    return "Pong!"


def uptime(start_timestamp: float) -> str:
    """Format bot uptime into a human-readable string.

    Args:
        start_timestamp: Unix timestamp when the bot started.

    Returns:
        Formatted uptime string or UptimeInfo object if return_raw is True.
    """
    # Calculate uptime in hours, minutes, and seconds.
    uptime_seconds = int(time.time() - start_timestamp)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    # Build the uptime string.
    parts = []
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds > 0 or not parts:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

    return f"Bot Uptime: {' '.join(parts)}."
