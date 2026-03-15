"""Core shared commands for all platforms."""

from .features.fun import diceroll, coinflip
from .features.utility import echo, ping, uptime

__all__ = ["diceroll", "coinflip", "echo", "ping", "uptime"]
