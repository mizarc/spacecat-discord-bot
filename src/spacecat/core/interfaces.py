from abc import ABC, abstractmethod
from typing import Any


class BaseDispatcher(ABC):
    """The Contract for all platform dispatchers.

    Any platform (Fluxer, Discord, etc.) must implement these methods
    for the Event and Reminder system to work.
    """

    @abstractmethod
    async def dispatch_reminder(self, channel_id: int, message_id: int, content: str) -> None:
        """Sends a plain text message reply as a reminder."""

    @abstractmethod
    async def dispatch_message(self, channel_id: int | str, content: str) -> None:
        """Sends a plain text message to a channel."""

    @abstractmethod
    async def dispatch_embed(self, channel_id: int | str, **kwargs: Any) -> None:
        """Sends a rich embed/card to a channel."""

    @abstractmethod
    async def dispatch_voice_move(self, source_channel: int, destination_channel: int) -> None:
        """Moves a user from one voice channel to another."""
