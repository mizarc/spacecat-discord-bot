"""Shared utility command logic."""

import time
from typing import NamedTuple, TypedDict


class UserData(NamedTuple):
    """User information container."""

    id: str
    username: str
    display_name: str | None
    discriminator: str | None
    avatar_url: str | None
    created_at: str | None
    is_bot: str | None
    status: str | None
    roles: str | None


class ServerData(NamedTuple):
    """Server information container."""

    id: str
    name: str
    owner_id: str | None
    member_count: str | None
    created_at: str | None
    icon_url: str | None
    features: str | None
    roles: str | None
    channels: str | None


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


def serverinfo(server_data: ServerData) -> UniversalEmbed:
    """Display the server's information.

    This leverages a universal embed format with server-specific
    information that can be parsed by the individual platforms.

    Args:
        server_data: The server's data.

    Returns:
        A UniversalEmbed object that stores metadata for the platform
        to parse into a formatted layout.
    """
    # Required embed field.
    fields: list[EmbedField] = [
        {"name": "Server ID", "value": server_data.id, "inline": True},
        {"name": "Server Name", "value": server_data.name, "inline": True},
    ]

    # Optional fields that can be applied to the embed.
    if server_data.owner_id:
        fields.append({"name": "Owner ID", "value": server_data.owner_id, "inline": True})
    if server_data.member_count:
        fields.append({"name": "Member Count", "value": server_data.member_count, "inline": True})
    if server_data.created_at:
        fields.append({"name": "Server Created", "value": server_data.created_at, "inline": True})
    if server_data.features:
        fields.append({"name": "Features", "value": server_data.features, "inline": False})
    if server_data.roles:
        fields.append({"name": "Roles", "value": server_data.roles, "inline": False})
    if server_data.channels:
        fields.append({"name": "Channels", "value": server_data.channels, "inline": False})

    return {
        "title": f"Server: {server_data.name}",
        "fields": fields,
        "color": 0x3498DB,
    }


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


def userinfo(user_data: UserData) -> UniversalEmbed:
    """Display the user's server profile info.

    This leverages a universal embed format with user-specific
    information that can be parsed by the individual platforms.

    Args:
        user_data: The user's profile data.

    Returns:
        A UniversalEmbed object that stores metadata for the platform
        to parse into a formatted layout.
    """
    # Required embed field.
    fields: list[EmbedField] = [
        {"name": "User ID", "value": user_data.id, "inline": True},
    ]

    # Optional fields that can be applied to the embed.
    if user_data.display_name:
        fields.append({"name": "Display Name", "value": user_data.display_name, "inline": True})
    if user_data.discriminator:
        fields.append(
            {"name": "Discriminator", "value": f"#{user_data.discriminator}", "inline": True}
        )
    if user_data.created_at:
        fields.append({"name": "Account Created", "value": user_data.created_at, "inline": True})
    if user_data.is_bot:
        fields.append({"name": "Bot User", "value": "🤖 Yes", "inline": True})
    if user_data.status:
        fields.append({"name": "Status", "value": user_data.status, "inline": True})
    if user_data.roles:
        fields.append({"name": "Roles", "value": user_data.roles, "inline": False})

    # Return the final embed object
    return {
        "title": f"Profile: {user_data.username}",
        "fields": fields,
        "color": 0x3498DB,
    }
