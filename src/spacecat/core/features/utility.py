"""Shared utility command logic."""

import time
from typing import NamedTuple


class UptimeInfo(NamedTuple):
    """Uptime information container."""
    hours: int
    minutes: int
    seconds: int


def format_uptime(start_time: float) -> UptimeInfo:
    """Calculate uptime from a start timestamp.
    
    Args:
        start_time: Unix timestamp when the process started.
        
    Returns:
        UptimeInfo with hours, minutes, and seconds.
    """
    uptime_seconds = int(time.time() - start_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return UptimeInfo(hours=hours, minutes=minutes, seconds=seconds)


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
